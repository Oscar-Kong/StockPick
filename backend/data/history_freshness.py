"""Assess whether stored OHLC history is sufficient and fresh enough to serve."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

NY_TZ = ZoneInfo("America/New_York")

# During regular hours, allow one completed session of lag before forcing refresh.
_MAX_SESSION_LAG = 1


@dataclass(frozen=True)
class HistoryFreshnessInfo:
    last_date: date | None
    bar_count: int
    is_sufficient: bool
    is_fresh: bool
    session_lag: int
    needs_refresh: bool
    expected_last_session: date | None
    source: str = "local"

    def to_metadata(self) -> dict[str, Any]:
        return {
            "price_history_last_date": self.last_date.isoformat() if self.last_date else None,
            "price_history_bar_count": self.bar_count,
            "price_history_is_stale": not self.is_fresh,
            "price_history_source": self.source,
        }


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _to_date(ts: Any) -> date | None:
    if ts is None:
        return None
    try:
        return pd.Timestamp(ts).date()
    except Exception:
        return None


def _last_bar_date(df: pd.DataFrame) -> date | None:
    if df is None or df.empty or "date" not in df.columns:
        return None
    return _to_date(df["date"].max())


def expected_last_completed_session(now: datetime | None = None) -> date:
    """
    Most recent US equity session that should have a completed daily bar.

    Before the regular close on a trading day, the last *completed* session is
    the prior session — today's bar is not required mid-session.
    """
    now_et = (now or _utcnow()).replace(tzinfo=timezone.utc).astimezone(NY_TZ)
    try:
        import exchange_calendars as xcals
        from config import SCHEDULER_MARKET_CALENDAR

        cal = xcals.get_calendar(SCHEDULER_MARKET_CALENDAR)
        today = pd.Timestamp(now_et.date(), tz=NY_TZ)
        if cal.is_session(today):
            if now_et.time() >= time(16, 0):
                return today.date()
            prev = cal.previous_session(today)
            return prev.date()
        prev = cal.previous_session(today)
        return prev.date()
    except Exception:
        d = now_et.date()
        while d.weekday() >= 5:
            d -= timedelta(days=1)
        if now_et.time() >= time(16, 0) and d.weekday() < 5:
            return d
        # Step back to previous weekday (conservative holiday fallback)
        d -= timedelta(days=1)
        while d.weekday() >= 5:
            d -= timedelta(days=1)
        return d


def session_lag_business_days(last: date, expected: date) -> int:
    """Sessions between last bar date and expected (0 = up to date)."""
    if last >= expected:
        return 0
    try:
        import exchange_calendars as xcals
        from config import SCHEDULER_MARKET_CALENDAR

        cal = xcals.get_calendar(SCHEDULER_MARKET_CALENDAR)
        start = pd.Timestamp(last, tz=NY_TZ)
        end = pd.Timestamp(expected, tz=NY_TZ)
        sessions = cal.sessions_in_range(start, end)
        # Exclude the last bar date itself; count sessions strictly after last.
        count = sum(1 for s in sessions if s.date() > last)
        return max(0, count)
    except Exception:
        lag = 0
        cur = last + timedelta(days=1)
        while cur <= expected:
            if cur.weekday() < 5:
                lag += 1
            cur += timedelta(days=1)
        return lag


def assess_history_freshness(
    df: pd.DataFrame,
    min_bars: int,
    *,
    now: datetime | None = None,
    source: str = "local",
    max_session_lag: int | None = None,
) -> HistoryFreshnessInfo:
    bar_count = len(df) if df is not None and not df.empty else 0
    last = _last_bar_date(df)
    expected = expected_last_completed_session(now)
    is_sufficient = bar_count >= min_bars
    lag = session_lag_business_days(last, expected) if last else 999
    allowed_lag = _MAX_SESSION_LAG if max_session_lag is None else int(max_session_lag)
    is_fresh = is_sufficient and last is not None and lag <= allowed_lag
    needs_refresh = not is_fresh and (not is_sufficient or lag > allowed_lag)
    return HistoryFreshnessInfo(
        last_date=last,
        bar_count=bar_count,
        is_sufficient=is_sufficient,
        is_fresh=is_fresh,
        session_lag=lag if last else 999,
        needs_refresh=needs_refresh or not is_sufficient,
        expected_last_session=expected,
        source=source,
    )


def merge_history_frames(local: pd.DataFrame, provider: pd.DataFrame) -> pd.DataFrame:
    """Merge local and provider OHLC; provider wins on duplicate dates."""
    if local is None or local.empty:
        return provider.copy().reset_index(drop=True) if provider is not None else pd.DataFrame()
    if provider is None or provider.empty:
        return local.copy().reset_index(drop=True)
    combined = pd.concat([local, provider], ignore_index=True)
    combined["date"] = pd.to_datetime(combined["date"]).dt.normalize()
    combined = combined.sort_values("date")
    combined = combined.drop_duplicates(subset=["date"], keep="last")
    cols = ["date", "open", "high", "low", "close", "volume"]
    return combined[cols].reset_index(drop=True)
