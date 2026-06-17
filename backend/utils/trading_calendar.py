"""NYSE trading session utilities for forward-return math."""
from __future__ import annotations

from datetime import date, datetime
from functools import lru_cache
from typing import Any

import pandas as pd

from config import SCHEDULER_MARKET_CALENDAR


@lru_cache(maxsize=1)
def _calendar():
    try:
        import exchange_calendars as xcals
    except ImportError:
        return None
    return xcals.get_calendar(SCHEDULER_MARKET_CALENDAR)


def calendar_available() -> bool:
    return _calendar() is not None


def to_session_date(ts: Any) -> date | None:
    try:
        return pd.Timestamp(ts).date()
    except Exception:
        return None


def session_index_for_date(d: date) -> int | None:
    """Index into calendar sessions on or after d."""
    cal = _calendar()
    if cal is None:
        return None
    sessions = cal.sessions
    try:
        sess = cal.date_to_session(d, direction="next")
        return int(sessions.get_loc(sess))
    except Exception:
        ts = pd.Timestamp(d)
        if getattr(sessions, "tz", None) is not None:
            ts = ts.tz_localize(sessions.tz) if ts.tz is None else ts.tz_convert(sessions.tz)
        idx = sessions.searchsorted(ts, side="left")
        if idx >= len(sessions):
            return None
        return int(idx)


def forward_session_index(start_idx: int, horizon_sessions: int) -> int | None:
    cal = _calendar()
    if cal is None:
        return None
    end = start_idx + horizon_sessions
    if end >= len(cal.sessions):
        return None
    return end


def session_date_at(index: int) -> str | None:
    cal = _calendar()
    if cal is None:
        return None
    if index < 0 or index >= len(cal.sessions):
        return None
    return str(cal.sessions[index].date())


def align_price_index_to_session(df: pd.DataFrame, session_date: date) -> int | None:
    """Find row index in OHLC df matching or after session_date."""
    if df is None or df.empty:
        return None
    target = session_date
    col = df["date"] if "date" in df.columns else df.index
    for i, ts in enumerate(col):
        d = to_session_date(ts)
        if d is not None and d >= target:
            return i
    return len(df) - 1


def forward_return_sessions(
    hist: pd.DataFrame,
    start_date: date,
    horizon_sessions: int,
) -> float | None:
    """Return % change over horizon_sessions NYSE sessions."""
    if hist is None or hist.empty:
        return None
    start_idx = align_price_index_to_session(hist, start_date)
    if start_idx is None:
        return None
    sess_idx = session_index_for_date(start_date)
    if sess_idx is None:
        return None
    end_sess = forward_session_index(sess_idx, horizon_sessions)
    if end_sess is None:
        return None
    end_date_str = session_date_at(end_sess)
    if not end_date_str:
        return None
    end_idx = align_price_index_to_session(hist, date.fromisoformat(end_date_str))
    if end_idx is None or end_idx <= start_idx:
        return None
    p0 = float(hist["close"].iloc[start_idx])
    p1 = float(hist["close"].iloc[end_idx])
    if p0 <= 0:
        return None
    return round((p1 / p0 - 1) * 100, 4)
