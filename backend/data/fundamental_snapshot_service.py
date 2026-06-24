"""Cached fundamental snapshots for scan — avoid live multi-provider reconciliation every tick."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from config import FUNDAMENTAL_SNAPSHOT_MAX_AGE_DAYS
from data.historical_store import HistoricalStore
from data.reconciler import DataReconciler, ReconcileResult

logger = logging.getLogger(__name__)

COMPOUNDER_FUNDAMENTAL_FIELDS = (
    "revenueGrowth",
    "earningsGrowth",
    "profitMargins",
    "grossMargins",
    "operatingMargins",
    "freeCashflow",
    "returnOnEquity",
    "debtToEquity",
    "marketCap",
    "trailingPE",
    "sector",
    "industry",
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _parse_snapshot_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d")
    except ValueError:
        return None


def _snapshot_is_fresh(snapshot_date: str | None, *, max_age_days: int | None = None) -> bool:
    parsed = _parse_snapshot_date(snapshot_date)
    if parsed is None:
        return False
    age_limit = max_age_days if max_age_days is not None else FUNDAMENTAL_SNAPSHOT_MAX_AGE_DAYS
    return (_utcnow().date() - parsed.date()) <= timedelta(days=age_limit)


def _reconcile_from_payload(rec_dict: dict | None, symbol: str) -> ReconcileResult | None:
    if not rec_dict:
        return None
    return ReconcileResult(
        symbol=symbol.upper(),
        canonical=rec_dict.get("canonical", {}),
        quality_score=rec_dict.get("quality_score", 0),
        source_audit=rec_dict.get("source_audit", {}),
        flags=rec_dict.get("flags", []),
    )


def _missing_compounder_fields(info: dict, fundamentals: dict) -> list[str]:
    missing: list[str] = []
    mapping = {
        "revenue_growth": info.get("revenueGrowth") or fundamentals.get("revenue_growth"),
        "revenue_growth_consistency": fundamentals.get("revenue_growth_consistency"),
        "eps_growth": info.get("earningsGrowth") or fundamentals.get("earnings_growth"),
        "gross_margin": info.get("grossMargins") or fundamentals.get("gross_margin"),
        "operating_margin": info.get("operatingMargins") or fundamentals.get("operating_margin"),
        "free_cash_flow": info.get("freeCashflow") or fundamentals.get("free_cash_flow"),
        "return_on_equity": info.get("returnOnEquity") or fundamentals.get("return_on_equity"),
        "return_on_invested_capital": fundamentals.get("roic") or fundamentals.get("return_on_invested_capital"),
        "debt_to_equity": info.get("debtToEquity") or fundamentals.get("debt_to_equity"),
        "share_dilution": fundamentals.get("share_dilution"),
        "valuation_pe": info.get("trailingPE") or fundamentals.get("pe_ratio"),
        "market_cap": info.get("marketCap") or fundamentals.get("market_cap"),
        "sector": info.get("sector") or fundamentals.get("sector"),
        "industry": info.get("industry") or fundamentals.get("industry"),
    }
    for key, value in mapping.items():
        if value is None or value == "":
            missing.append(key)
    return missing


def _confidence_penalty(missing_fields: list[str]) -> float:
    """Reduce confidence when fundamentals are absent — not the same as a zero factor score."""
    return min(35.0, float(len(missing_fields)) * 3.0)


@dataclass
class FundamentalLoadResult:
    info: dict
    fundamentals: dict
    reconcile: ReconcileResult | None
    snapshot_date: str | None = None
    source: str | None = None
    from_cache: bool = False
    refreshed: bool = False
    missing_fields: list[str] = field(default_factory=list)
    confidence_penalty: float = 0.0
    warnings: list[str] = field(default_factory=list)

    def apply_to_info(self, info: dict) -> None:
        info["_fundamental_snapshot_date"] = self.snapshot_date
        info["_fundamental_source"] = self.source
        info["_fundamental_from_cache"] = self.from_cache
        info["_fundamental_refreshed"] = self.refreshed
        info["_missing_fundamental_fields"] = list(self.missing_fields)
        info["_fundamental_confidence_penalty"] = round(self.confidence_penalty, 1)
        if self.warnings:
            info["_fundamental_warnings"] = list(self.warnings)
        if self.reconcile:
            info["_reconcile_quality"] = self.reconcile.quality_score
            info["_reconcile_flags"] = self.reconcile.flags


def resolve_fundamentals_for_scan(
    symbol: str,
    *,
    policy: str = "cache_first",
) -> FundamentalLoadResult:
    """Load fundamentals for Stage B compounder scans with cache-first reconciliation."""
    sym = symbol.upper()
    store = HistoricalStore()
    cached = store.get_latest_fundamental_snapshot(sym)

    if cached and _snapshot_is_fresh(cached.get("snapshot_date")):
        payload = cached.get("payload") or {}
        info = dict(payload.get("info") or {})
        fundamentals = dict(payload.get("fundamentals") or {})
        rec = _reconcile_from_payload(payload.get("reconcile"), sym)
        missing = _missing_compounder_fields(info, fundamentals)
        warnings = []
        if missing:
            warnings.append(f"missing_fundamentals:{','.join(missing[:8])}")
        return FundamentalLoadResult(
            info=info,
            fundamentals=fundamentals,
            reconcile=rec,
            snapshot_date=cached.get("snapshot_date"),
            source=cached.get("source"),
            from_cache=True,
            refreshed=False,
            missing_fields=missing,
            confidence_penalty=_confidence_penalty(missing),
            warnings=warnings,
        )

    if policy == "cache_only":
        missing = _missing_compounder_fields({}, {})
        return FundamentalLoadResult(
            info={},
            fundamentals={},
            reconcile=None,
            missing_fields=missing,
            confidence_penalty=_confidence_penalty(missing),
            warnings=["fundamental_snapshot_missing"],
        )

    info, fundamentals, rec = DataReconciler().get_canonical_fundamentals(sym)
    missing = _missing_compounder_fields(info, fundamentals)
    warnings = list(rec.flags) if rec else []
    if missing:
        warnings.append(f"missing_fundamentals:{','.join(missing[:8])}")

    store.save_fundamentals(
        sym,
        {"info": info, "fundamentals": fundamentals, "reconcile": rec.to_dict() if rec else {}},
        source="reconciled",
        quality_score=rec.quality_score if rec else None,
    )
    today = _utcnow().strftime("%Y-%m-%d")
    return FundamentalLoadResult(
        info=info,
        fundamentals=fundamentals,
        reconcile=rec,
        snapshot_date=today,
        source="reconciled",
        from_cache=False,
        refreshed=True,
        missing_fields=missing,
        confidence_penalty=_confidence_penalty(missing),
        warnings=warnings,
    )


def build_scan_diagnostics(
    *,
    history_period: str,
    history_bars: int,
    history_source: str,
    fundamental: FundamentalLoadResult | None = None,
) -> dict[str, Any]:
    diag: dict[str, Any] = {
        "price_history_period": history_period,
        "price_history_bars": history_bars,
        "price_history_source": history_source,
    }
    if fundamental is not None:
        diag.update(
            {
                "fundamental_snapshot_date": fundamental.snapshot_date,
                "fundamental_source": fundamental.source,
                "reconciliation_quality": (
                    fundamental.reconcile.quality_score if fundamental.reconcile else None
                ),
                "missing_fundamental_fields": list(fundamental.missing_fields),
                "confidence_penalty": fundamental.confidence_penalty,
                "fundamental_from_cache": fundamental.from_cache,
                "fundamental_refreshed": fundamental.refreshed,
                "fundamental_warnings": list(fundamental.warnings),
            }
        )
    return diag
