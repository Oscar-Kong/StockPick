"""Build and query forward return label panel."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import pandas as pd
from sqlalchemy.orm import Session

from config import PREDICTION_OUTCOME_HORIZONS
from data.db_engine import get_engine
from data.price_service import PriceService
from data.sector_map import sector_etf
from engines.quant_models import ForwardReturnLabel
from utils.trading_calendar import forward_return_sessions, to_session_date

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _panel_symbols() -> list[str]:
    try:
        from data.cache import Cache

        cached = Cache().get("universe:sp500")
        if cached and cached.get("symbols"):
            return [s.upper() for s in cached["symbols"][:80]]
    except Exception:
        pass
    return ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "JPM", "V", "UNH", "XOM"]


def build_forward_labels(
    *,
    symbols: list[str] | None = None,
    horizons: list[int] | None = None,
    lookback_days: int = 400,
) -> dict:
    symbols = symbols or _panel_symbols()
    horizons = horizons or PREDICTION_OUTCOME_HORIZONS
    ps = PriceService()
    spy_hist = ps.get_spy_history(period="2y")
    sector_cache: dict[str, pd.DataFrame] = {}
    engine = get_engine()
    written = 0

    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=lookback_days)

    with Session(engine) as session:
        for sym in symbols:
            hist = ps.get_history(sym, period="2y")
            if hist.empty:
                continue
            hist = hist.reset_index(drop=True)
            info_sector = None
            try:
                from data.reconciler import DataReconciler

                info, _, _ = DataReconciler().get_canonical_fundamentals(sym)
                info_sector = info.get("sector") if info else None
            except Exception:
                pass
            etf = sector_etf(info_sector) if info_sector else None
            sec_hist = sector_cache.get(etf) if etf else None
            if etf and sec_hist is None:
                sec_hist = ps.get_history(etf, period="2y")
                sector_cache[etf] = sec_hist

            dates: list = []
            col = hist["date"] if "date" in hist.columns else hist.index
            for ts in col:
                d = to_session_date(ts)
                if d and start <= d <= end:
                    dates.append(d)

            for d in dates[-120:]:
                as_of = d.isoformat()
                for h in horizons:
                    fwd = forward_return_sessions(hist, d, h)
                    if fwd is None:
                        continue
                    spy_fwd = forward_return_sessions(spy_hist.reset_index(drop=True), d, h)
                    sec_fwd = (
                        forward_return_sessions(sec_hist.reset_index(drop=True), d, h)
                        if sec_hist is not None and not sec_hist.empty
                        else None
                    )
                    row = (
                        session.query(ForwardReturnLabel)
                        .filter(
                            ForwardReturnLabel.symbol == sym,
                            ForwardReturnLabel.as_of_date == as_of,
                            ForwardReturnLabel.horizon_days == h,
                        )
                        .first()
                    )
                    payload = dict(
                        symbol=sym,
                        as_of_date=as_of,
                        horizon_days=h,
                        fwd_return=fwd,
                        excess_vs_spy=round(fwd - spy_fwd, 4) if spy_fwd is not None else None,
                        excess_vs_sector=round(fwd - sec_fwd, 4) if sec_fwd is not None else None,
                        max_drawdown=None,
                        sector=info_sector,
                        updated_at=_utcnow(),
                    )
                    if row:
                        for k, v in payload.items():
                            setattr(row, k, v)
                    else:
                        session.add(ForwardReturnLabel(**payload))
                    written += 1
        session.commit()

    return {"symbols": len(symbols), "labels_written": written, "horizons": horizons}
