"""Build screener candidates with reconciled fundamentals and reliable OHLC."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from data.historical_store import HistoricalStore
from data.price_service import PriceService, avg_volume_from_history
from data.reconciler import DataReconciler, ReconcileResult
from screeners.base import CandidateContext

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _load_cached_fundamentals(symbol: str) -> tuple[dict, dict, ReconcileResult | None]:
    """Use today's reconciled snapshot if available."""
    store = HistoricalStore()
    session = store._get_session()
    try:
        from data.historical_store import FundamentalSnapshot

        today = _utcnow().strftime("%Y-%m-%d")
        row = (
            session.query(FundamentalSnapshot)
            .filter(
                FundamentalSnapshot.symbol == symbol.upper(),
                FundamentalSnapshot.snapshot_date == today,
            )
            .first()
        )
        if not row or not row.data_json:
            return {}, {}, None
        payload = json.loads(row.data_json)
        info = payload.get("info") or {}
        fundamentals = payload.get("fundamentals") or {}
        rec_dict = payload.get("reconcile")
        rec = None
        if rec_dict:
            from data.reconciler import ReconcileResult

            rec = ReconcileResult(
                symbol=symbol.upper(),
                canonical=rec_dict.get("canonical", {}),
                quality_score=rec_dict.get("quality_score", 0),
                source_audit=rec_dict.get("source_audit", {}),
                flags=rec_dict.get("flags", []),
            )
        return info, fundamentals, rec
    finally:
        session.close()


def build_candidate(
    symbol: str,
    *,
    history_period: str = "1y",
    include_spy: bool = False,
    spy_period: str = "1y",
    reconcile: bool = True,
    price_service: PriceService | None = None,
) -> CandidateContext | None:
    """Enrich symbol with DB-first prices and multi-source fundamentals."""
    ps = price_service or PriceService()
    sym = symbol.upper()

    hist = ps.get_history(sym, period=history_period)
    if hist.empty:
        return None

    info: dict = {}
    fundamentals: dict = {}
    rec: ReconcileResult | None = None

    if reconcile:
        cached_info, cached_fund, cached_rec = _load_cached_fundamentals(sym)
        if cached_info and cached_rec and cached_rec.quality_score > 0:
            info, fundamentals, rec = cached_info, cached_fund, cached_rec
        else:
            info, fundamentals, rec = DataReconciler().get_canonical_fundamentals(sym)
    else:
        info = ps.yf.get_info(sym)

    # Price: prefer reconciled, then last bar (most accurate for screening)
    last_close = float(hist["close"].iloc[-1])
    price = float(info.get("currentPrice") or last_close)
    if rec and rec.canonical.get("price"):
        # If reconcile price diverges >5% from last bar, trust the bar for screening
        rec_price = float(rec.canonical["price"])
        if abs(rec_price - last_close) / max(last_close, 1e-9) <= 0.05:
            price = rec_price
        else:
            info["_price_note"] = "Using last close; sources disagreed on price"
            price = last_close
    else:
        price = last_close

    # Volume from bars (more reliable than stale info.averageVolume)
    hist_vol = avg_volume_from_history(hist)
    if hist_vol > 0:
        info["averageVolume"] = hist_vol

    if rec:
        info["_reconcile_quality"] = rec.quality_score
        info["_reconcile_flags"] = rec.flags
        HistoricalStore().save_fundamentals(
            sym,
            {"info": info, "fundamentals": fundamentals, "reconcile": rec.to_dict()},
            source="reconciled",
            quality_score=rec.quality_score,
        )

    spy_hist = ps.get_spy_history(spy_period) if include_spy else None

    return CandidateContext(
        symbol=sym,
        price=price,
        info=info,
        fundamentals=fundamentals,
        history=hist,
        spy_history=spy_hist,
    )
