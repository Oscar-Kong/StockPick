"""Build screener candidates with reconciled fundamentals and reliable OHLC."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

import pandas as pd

from data.fundamental_snapshot_service import (
    FundamentalLoadResult,
    build_scan_diagnostics,
    resolve_fundamentals_for_scan,
)
from data.historical_store import HistoricalStore
from data.history_normalize import normalize_ohlc_history
from data.price_service import PriceService, avg_volume_from_history
from data.reconciler import DataReconciler, ReconcileResult
from screeners.base import CandidateContext

logger = logging.getLogger(__name__)

HISTORY_SOURCE_BULK = "stage_a_bulk"
HISTORY_SOURCE_PROVIDER = "provider_fallback"
HISTORY_SOURCE_PRICE_SERVICE = "price_service"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _load_cached_fundamentals(symbol: str) -> tuple[dict, dict, ReconcileResult | None]:
    """Use today's reconciled snapshot if available."""
    row = HistoricalStore().get_latest_fundamental_snapshot(symbol)
    if not row:
        return {}, {}, None
    payload = row.get("payload") or {}
    info = payload.get("info") or {}
    fundamentals = payload.get("fundamentals") or {}
    rec_dict = payload.get("reconcile")
    rec = None
    if rec_dict:
        rec = ReconcileResult(
            symbol=symbol.upper(),
            canonical=rec_dict.get("canonical", {}),
            quality_score=rec_dict.get("quality_score", 0),
            source_audit=rec_dict.get("source_audit", {}),
            flags=rec_dict.get("flags", []),
        )
    return info, fundamentals, rec


def build_candidate(
    symbol: str,
    *,
    history_period: str = "1y",
    include_spy: bool = False,
    spy_period: str = "1y",
    reconcile: bool = True,
    price_service: PriceService | None = None,
    history: pd.DataFrame | None = None,
    history_source: str | None = None,
    fundamentals_policy: str = "live",
) -> CandidateContext | None:
    """Enrich symbol with DB-first prices and multi-source fundamentals."""
    ps = price_service or PriceService()
    sym = symbol.upper()
    resolved_source = history_source
    fundamental_load: FundamentalLoadResult | None = None

    if history is not None:
        hist = normalize_ohlc_history(history)
        if hist is None or hist.empty:
            return None
        hist = PriceService._trim_period(hist, history_period)
        resolved_source = history_source or "preloaded"
    else:
        hist = ps.get_history(sym, period=history_period)
        resolved_source = history_source or HISTORY_SOURCE_PRICE_SERVICE
    if hist.empty:
        return None

    info: dict = {}
    fundamentals: dict = {}
    rec: ReconcileResult | None = None

    if reconcile:
        if fundamentals_policy == "cache_first":
            fundamental_load = resolve_fundamentals_for_scan(sym, policy="cache_first")
            info = dict(fundamental_load.info)
            fundamentals = dict(fundamental_load.fundamentals)
            rec = fundamental_load.reconcile
            fundamental_load.apply_to_info(info)
        else:
            cached_info, cached_fund, cached_rec = _load_cached_fundamentals(sym)
            if cached_info and cached_rec and cached_rec.quality_score > 0:
                info, fundamentals, rec = cached_info, cached_fund, cached_rec
            else:
                info, fundamentals, rec = DataReconciler().get_canonical_fundamentals(sym)
                HistoricalStore().save_fundamentals(
                    sym,
                    {"info": info, "fundamentals": fundamentals, "reconcile": rec.to_dict()},
                    source="reconciled",
                    quality_score=rec.quality_score,
                )
            info["_reconcile_quality"] = rec.quality_score if rec else None
            info["_reconcile_flags"] = rec.flags if rec else []
    else:
        info = ps.get_info(sym)
        if not info.get("currentPrice") and not info.get("marketCap"):
            hist_quote = ps.quote_from_history(sym, hist)
            if hist_quote:
                info = {**hist_quote, **info}

    info["_history_source"] = resolved_source
    info["_history_period"] = history_period
    info["_history_bars"] = len(hist)
    if resolved_source == HISTORY_SOURCE_BULK:
        info["_history_from_bulk_scan"] = True

    info["_scan_diagnostics"] = build_scan_diagnostics(
        history_period=history_period,
        history_bars=len(hist),
        history_source=resolved_source,
        fundamental=fundamental_load,
    )

    last_close = float(hist["close"].iloc[-1])
    price = float(info.get("currentPrice") or last_close)
    if rec and rec.canonical.get("price"):
        rec_price = float(rec.canonical["price"])
        if abs(rec_price - last_close) / max(last_close, 1e-9) <= 0.05:
            price = rec_price
        else:
            info["_price_note"] = "Using last close; sources disagreed on price"
            price = last_close
    else:
        price = last_close

    hist_vol = avg_volume_from_history(hist)
    if hist_vol > 0:
        info["averageVolume"] = hist_vol

    if rec and fundamentals_policy != "cache_first":
        info["_reconcile_quality"] = rec.quality_score
        info["_reconcile_flags"] = rec.flags

    spy_hist = ps.get_spy_history(spy_period) if include_spy else None

    return CandidateContext(
        symbol=sym,
        price=price,
        info=info,
        fundamentals=fundamentals,
        history=hist,
        spy_history=spy_hist,
    )
