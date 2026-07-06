"""Pre-holiday and long-weekend exposure reduction signals."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from utils.trading_calendar import _calendar, calendar_available

NY_TZ = ZoneInfo("America/New_York")


@dataclass(frozen=True)
class HolidayRiskAssessment:
  is_pre_holiday_session: bool
  recommend_reduce_exposure: bool
  reason: str | None


def _next_trading_session(after: date) -> date | None:
  cal = _calendar()
  if cal is None:
    # Weekday fallback: skip Sat/Sun
    d = after + timedelta(days=1)
    while d.weekday() >= 5:
      d += timedelta(days=1)
    return d
  try:
    import pandas as pd

    sessions = cal.sessions
    ts = pd.Timestamp(after) + pd.Timedelta(days=1)
    idx = sessions.searchsorted(ts, side="left")
    if idx >= len(sessions):
      return None
    return sessions[idx].date()
  except Exception:
    return None


def _is_trading_session(d: date) -> bool:
  cal = _calendar()
  if cal is None:
    return d.weekday() < 5
  try:
    cal.date_to_session(d, direction="none")
    return True
  except Exception:
    return False


def assess_holiday_risk(now: datetime | None = None) -> HolidayRiskAssessment:
  """Flag sessions before exchange holidays or long weekends."""
  now_et = (now or datetime.now(timezone.utc)).astimezone(NY_TZ)
  today = now_et.date()
  if not _is_trading_session(today):
    return HolidayRiskAssessment(False, False, None)

  next_sess = _next_trading_session(today)
  if next_sess is None:
    return HolidayRiskAssessment(False, False, None)

  gap_days = (next_sess - today).days
  if gap_days >= 3:
    reason = (
      f"Next US equity session is {next_sess.isoformat()} "
      f"({gap_days} calendar days away) — reduce short-term exposure before long break"
    )
    return HolidayRiskAssessment(True, True, reason)
  if gap_days == 2 and today.weekday() == 4:
    reason = "Friday before a Monday holiday or long weekend — reduce short-term exposure"
    return HolidayRiskAssessment(True, True, reason)
  if gap_days >= 2:
    reason = f"Extended market closure after today (next session {next_sess.isoformat()})"
    return HolidayRiskAssessment(True, True, reason)
  return HolidayRiskAssessment(False, False, None)


def calendar_note() -> str:
  if calendar_available():
    return "NYSE calendar"
  return "weekday fallback (install exchange_calendars for holiday precision)"
