"""Point-in-time helpers for scan evaluation — no look-ahead."""
from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from data.pit_history import truncate_history
from utils.trading_calendar import (
    align_price_index_to_session,
    forward_return_sessions,
    session_date_at,
    session_index_for_date,
    forward_session_index,
)

DEFAULT_FORWARD_HORIZONS = (1, 5, 20, 60)


def quotes_to_dataframe(quotes: list[dict]) -> pd.DataFrame:
    if not quotes:
        return pd.DataFrame()
    df = pd.DataFrame(quotes)
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"]).dt.date
    return df.reset_index(drop=True)


def load_price_panel_from_store(
    symbols: list[str],
    *,
    limit: int = 600,
    store: Any | None = None,
) -> dict[str, pd.DataFrame]:
    """Load OHLC from HistoricalStore (offline-first)."""
    from data.historical_store import HistoricalStore

    hs = store or HistoricalStore()
    panel: dict[str, pd.DataFrame] = {}
    for sym in symbols:
        quotes = hs.get_quotes(sym.upper(), limit=limit)
        if quotes:
            panel[sym.upper()] = quotes_to_dataframe(quotes)
    return panel


def truncate_price_panel(panel: dict[str, pd.DataFrame], as_of: date) -> dict[str, pd.DataFrame]:
    out: dict[str, pd.DataFrame] = {}
    for sym, hist in panel.items():
        trimmed = truncate_history(hist, as_of)
        if not trimmed.empty:
            out[sym] = trimmed
    return out


def assert_no_lookahead(hist: pd.DataFrame, as_of: date) -> None:
    """Raise if any row date exceeds as_of."""
    if hist is None or hist.empty or "date" not in hist.columns:
        return
    max_date = pd.to_datetime(hist["date"]).max()
    if max_date.date() > as_of:
        raise ValueError(f"Look-ahead detected: max date {max_date.date()} > as_of {as_of}")


def forward_return_pct(
    hist_full: pd.DataFrame,
    as_of: date,
    horizon_sessions: int,
) -> float | None:
    """Session-accurate forward return (%). Uses full history for future bars only after as_of."""
    ret = forward_return_sessions(hist_full, as_of, horizon_sessions)
    if ret is not None:
        return ret
    return _forward_return_index_fallback(hist_full, as_of, horizon_sessions)


def _forward_return_index_fallback(
    hist: pd.DataFrame,
    as_of: date,
    horizon_sessions: int,
) -> float | None:
    """Business-day index fallback when exchange_calendars is unavailable."""
    if hist is None or hist.empty:
        return None
    start_idx = align_price_index_to_session(hist, as_of)
    if start_idx is None:
        return None
    end_idx = start_idx + horizon_sessions
    if end_idx >= len(hist):
        return None
    p0 = float(hist["close"].iloc[start_idx])
    p1 = float(hist["close"].iloc[end_idx])
    if p0 <= 0:
        return None
    return round((p1 / p0 - 1) * 100, 4)


def forward_path_excursions(
    hist_full: pd.DataFrame,
    as_of: date,
    horizon_sessions: int,
) -> dict[str, float | None]:
    """Max adverse / favorable excursion (% from entry close) over forward window."""
    if hist_full is None or hist_full.empty:
        return {"mae_pct": None, "mfe_pct": None}

    start_idx = align_price_index_to_session(hist_full, as_of)
    if start_idx is None:
        return {"mae_pct": None, "mfe_pct": None}

    end_idx: int | None = None
    sess_idx = session_index_for_date(as_of)
    if sess_idx is not None:
        end_sess = forward_session_index(sess_idx, horizon_sessions)
        if end_sess is not None:
            end_date_str = session_date_at(end_sess)
            if end_date_str:
                end_idx = align_price_index_to_session(hist_full, date.fromisoformat(end_date_str))
    if end_idx is None:
        end_idx = start_idx + horizon_sessions
    if end_idx is None or end_idx <= start_idx or end_idx >= len(hist_full):
        return {"mae_pct": None, "mfe_pct": None}

    entry = float(hist_full["close"].iloc[start_idx])
    if entry <= 0:
        return {"mae_pct": None, "mfe_pct": None}

    window = hist_full.iloc[start_idx : end_idx + 1]
    lows = window["low"].astype(float) if "low" in window.columns else window["close"].astype(float)
    highs = window["high"].astype(float) if "high" in window.columns else window["close"].astype(float)
    mae = float(((lows.min() / entry) - 1.0) * 100.0)
    mfe = float(((highs.max() / entry) - 1.0) * 100.0)
    return {"mae_pct": round(mae, 4), "mfe_pct": round(mfe, 4)}


def apply_penny_friction(
    raw_return_pct: float | None,
    *,
    spread_bps: float = 50.0,
    slippage_bps: float = 25.0,
    liquidity_penalty_bps: float = 0.0,
) -> float | None:
    """Haircut forward return for penny liquidity / spread / slippage (research only)."""
    if raw_return_pct is None:
        return None
    total_bps = spread_bps + slippage_bps + liquidity_penalty_bps
    return round(raw_return_pct - (total_bps / 100.0), 4)


def penny_liquidity_penalty_bps(metrics: dict[str, Any] | None) -> float:
    """Extra friction when ADV is low."""
    if not metrics:
        return 0.0
    adv = metrics.get("average_dollar_volume_20d")
    if adv is None:
        return 15.0
    adv_f = float(adv)
    if adv_f >= 2_000_000:
        return 0.0
    if adv_f >= 500_000:
        return 25.0
    return 75.0


def build_forward_outcomes(
    symbol: str,
    hist_full: pd.DataFrame,
    as_of: date,
    horizons: tuple[int, ...] | list[int],
    *,
    bucket: str,
    metrics: dict[str, Any] | None = None,
    apply_friction: bool = False,
    spread_bps: float = 50.0,
    slippage_bps: float = 25.0,
) -> dict[str, Any]:
    """Forward returns and excursions for all horizons."""
    out: dict[str, Any] = {"symbol": symbol.upper(), "horizons": {}}
    liq_penalty = penny_liquidity_penalty_bps(metrics) if bucket == "penny" else 0.0
    for h in horizons:
        raw = forward_return_pct(hist_full, as_of, int(h))
        adj = raw
        if apply_friction and bucket == "penny":
            adj = apply_penny_friction(
                raw,
                spread_bps=spread_bps,
                slippage_bps=slippage_bps,
                liquidity_penalty_bps=liq_penalty,
            )
        exc = forward_path_excursions(hist_full, as_of, int(h))
        out["horizons"][str(h)] = {
            "forward_return_pct": raw,
            "forward_return_adj_pct": adj,
            "mae_pct": exc["mae_pct"],
            "mfe_pct": exc["mfe_pct"],
            "delisted_or_incomplete": raw is None,
        }
    return out
