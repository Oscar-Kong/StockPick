"""Multi-source data reconciliation — cross-verify metrics across providers."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from config import (
    ALPHA_VANTAGE_API_KEY,
    FMP_API_KEY,
    FINNHUB_API_KEY,
    PRIMARY_FUNDAMENTALS_SOURCE,
    RECONCILE_PRICE_TOLERANCE,
    RECONCILE_RATIO_TOLERANCE,
)
from data.av_client import AlphaVantageClient
from data.fmp_client import FMPClient
from data.market_data_client import MarketDataClient

logger = logging.getLogger(__name__)

# Field mapping: canonical_name -> {source: field_name}
FIELD_MAP: dict[str, dict[str, str]] = {
    "price": {
        "finnhub": "currentPrice",
        "market": "currentPrice",
        "akshare": "currentPrice",
        "fmp": "price",
        "openbb": "currentPrice",
    },
    "pe_ratio": {
        "market": "trailingPE",
        "akshare": "trailingPE",
        "fmp": "pe_ratio",
        "av": "pe_ratio",
        "openbb": "pe_ratio",
    },
    "roe": {
        "market": "returnOnEquity",
        "fmp": "roe",
        "av": "return_on_equity",
        "openbb": "roe",
    },
    "revenue_ttm": {
        "market": "totalRevenue",
        "av": "revenue_ttm",
        "fmp": "revenue",
        "openbb": "totalRevenue",
    },
    "market_cap": {
        "market": "marketCap",
        "akshare": "marketCap",
        "fmp": "marketCap",
        "av": "market_cap",
        "openbb": "market_cap",
    },
    "profit_margin": {
        "market": "profitMargins",
        "fmp": "profit_margin",
        "av": "profit_margin",
        "openbb": "profit_margin",
    },
}


@dataclass
class FieldReconcileResult:
    field: str
    value: float | None
    sources: dict[str, float | None] = field(default_factory=dict)
    discarded: list[str] = field(default_factory=list)
    confidence: str = "low"  # low | medium | high
    notes: list[str] = field(default_factory=list)


@dataclass
class ReconcileResult:
    symbol: str
    canonical: dict[str, float | None] = field(default_factory=dict)
    fields: list[FieldReconcileResult] = field(default_factory=list)
    quality_score: float = 0.0
    source_audit: dict[str, str] = field(default_factory=dict)
    flags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "canonical": self.canonical,
            "quality_score": round(self.quality_score, 1),
            "source_audit": self.source_audit,
            "flags": self.flags,
            "fields": [
                {
                    "field": f.field,
                    "value": f.value,
                    "sources": f.sources,
                    "discarded": f.discarded,
                    "confidence": f.confidence,
                    "notes": f.notes,
                }
                for f in self.fields
            ],
        }


def _extract(source_data: dict, field_key: str) -> float | None:
    raw = source_data.get(field_key)
    if raw is None:
        return None
    try:
        v = float(raw)
        return v if v == v else None  # NaN check
    except (TypeError, ValueError):
        return None


def _relative_diff(a: float, b: float) -> float:
    denom = max(abs(a), abs(b), 1e-9)
    return abs(a - b) / denom


def _reconcile_numeric_field(
    field_name: str,
    values: dict[str, float | None],
    *,
    ratio_field: bool = False,
) -> FieldReconcileResult:
    tolerance = RECONCILE_RATIO_TOLERANCE if ratio_field else RECONCILE_PRICE_TOLERANCE
    clean = {k: v for k, v in values.items() if v is not None}
    result = FieldReconcileResult(field=field_name, value=None, sources=dict(values))

    if not clean:
        result.notes.append("No provider returned a value")
        return result

    if len(clean) == 1:
        src, val = next(iter(clean.items()))
        result.value = val
        result.confidence = "low"
        result.notes.append(f"Single source: {src}")
        return result

    # Median-based consensus; discard outliers beyond tolerance
    sorted_vals = sorted(clean.items(), key=lambda x: x[1])
    median = sorted_vals[len(sorted_vals) // 2][1]
    kept: dict[str, float] = {}
    discarded: list[str] = []

    for src, val in clean.items():
        if _relative_diff(val, median) <= tolerance:
            kept[src] = val
        else:
            discarded.append(src)
            result.notes.append(f"Discarded {src}={val:.4g} (>{tolerance*100:.0f}% from median)")

    result.discarded = discarded
    if kept:
        result.value = sum(kept.values()) / len(kept)
        if len(kept) >= 2:
            result.confidence = "high"
        else:
            result.confidence = "medium"
    else:
        result.value = median
        result.confidence = "low"
        result.notes.append("All sources inconsistent; using median")

    return result


class DataReconciler:
    """Multi-source reconciliation — FMP fundamentals, Finnhub quotes, AV fallback."""

    def __init__(self):
        self.market = MarketDataClient()
        self.av = AlphaVantageClient() if ALPHA_VANTAGE_API_KEY else None
        self.fmp = FMPClient() if FMP_API_KEY else None
        self.finnhub = None
        if FINNHUB_API_KEY:
            from data.finnhub_client import FinnhubClient

            self.finnhub = FinnhubClient()

    def fetch_all_sources(self, symbol: str) -> dict[str, dict]:
        sym = symbol.upper()
        sources: dict[str, dict] = {
            "market": {},
            "akshare": {},
            "fmp": {},
            "finnhub": {},
            "av": {},
            "openbb": {},
        }

        if self.finnhub:
            quote = self.finnhub.get_quote(sym)
            if quote:
                sources["finnhub"] = quote

        market_data = self.market.get_info(sym)
        if market_data:
            sources["market"] = market_data
            if market_data.get("source") == "akshare":
                sources["akshare"] = market_data

        use_fmp_primary = PRIMARY_FUNDAMENTALS_SOURCE == "fmp"
        market_has_core_fundamentals = bool(
            market_data.get("trailingPE")
            or market_data.get("returnOnEquity")
            or market_data.get("profitMargins")
        )

        if self.fmp and (use_fmp_primary or not market_has_core_fundamentals):
            profile = self.fmp.get_profile(sym)
            ratios = self.fmp.get_ratios(sym)
            bundle = self.fmp.get_fundamentals_bundle(sym)
            sources["fmp"] = {**profile, **ratios, **(bundle or {})}

        # Alpha Vantage: fallback / cross-validation
        if self.av:
            av_data = self.av.get_overview(sym)
            if av_data:
                sources["av"] = av_data

        try:
            from data.openbb_client import fetch_fundamentals_for_reconcile, is_available

            if is_available():
                obb_data = fetch_fundamentals_for_reconcile(sym)
                if obb_data:
                    sources["openbb"] = obb_data
        except Exception as exc:
            logger.debug("OpenBB reconcile fetch skipped for %s: %s", sym, exc)

        return sources

    def reconcile(self, symbol: str) -> ReconcileResult:
        sym = symbol.upper()
        raw = self.fetch_all_sources(sym)
        result = ReconcileResult(symbol=sym)

        ratio_fields = {"pe_ratio", "roe", "profit_margin"}

        for field_name, source_map in FIELD_MAP.items():
            values: dict[str, float | None] = {}
            for src, key in source_map.items():
                if src in raw:
                    values[src] = _extract(raw[src], key)

            fr = _reconcile_numeric_field(
                field_name,
                values,
                ratio_field=field_name in ratio_fields,
            )
            result.fields.append(fr)
            if fr.value is not None:
                result.canonical[field_name] = fr.value
                result.source_audit[field_name] = fr.confidence

        # Quality score: % of fields with high/medium confidence
        if result.fields:
            scored = sum(1 for f in result.fields if f.confidence in ("high", "medium"))
            result.quality_score = scored / len(result.fields) * 100

        if result.quality_score < 40:
            result.flags.append("Low cross-source agreement — verify manually")
        if not any(raw[s] for s in raw if s != "market") and (FMP_API_KEY or ALPHA_VANTAGE_API_KEY):
            result.flags.append("Secondary sources unavailable; single-source fallback only")
        elif not FMP_API_KEY and not ALPHA_VANTAGE_API_KEY:
            result.flags.append("Multi-source verification pending API keys")

        return result

    def get_canonical_fundamentals(self, symbol: str) -> tuple[dict, dict, ReconcileResult]:
        """Return (info, fundamentals, reconcile_result) for screener use."""
        sym = symbol.upper()
        raw = self.fetch_all_sources(sym)
        rec = self.reconcile(sym)

        if PRIMARY_FUNDAMENTALS_SOURCE == "fmp" and raw.get("fmp"):
            info = dict(raw["fmp"])
            fundamentals = dict(raw["fmp"])
        elif PRIMARY_FUNDAMENTALS_SOURCE == "akshare" and raw.get("market"):
            info = dict(raw.get("market") or {})
            fundamentals = dict(raw.get("market") or raw.get("av") or raw.get("fmp") or {})
        else:
            info = dict(raw.get("market") or {})
            fundamentals = dict(raw.get("av") or raw.get("fmp") or {})

        if raw.get("finnhub"):
            info.update({k: v for k, v in raw["finnhub"].items() if v is not None})

        # Overlay canonical reconciled values
        for k, v in rec.canonical.items():
            if v is None:
                continue
            if k == "price":
                info["currentPrice"] = v
            elif k == "pe_ratio":
                info["trailingPE"] = v
                fundamentals["pe_ratio"] = v
            elif k == "roe":
                info["returnOnEquity"] = v
                fundamentals["return_on_equity"] = v
            elif k == "revenue_ttm":
                fundamentals["revenue_ttm"] = v
            elif k == "market_cap":
                info["marketCap"] = v
                fundamentals["market_cap"] = v
            elif k == "profit_margin":
                info["profitMargins"] = v
                fundamentals["profit_margin"] = v

        if raw.get("fmp"):
            fmp = raw["fmp"]
            for key in ("sector", "industry", "beta"):
                if fmp.get(key) and not info.get(key):
                    info[key] = fmp[key]

        info["_reconcile_quality"] = rec.quality_score
        info["_reconcile_flags"] = rec.flags
        return info, fundamentals, rec
