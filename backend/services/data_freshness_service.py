"""Assess staleness for portfolio, prices, scans, and daily decisions."""
from __future__ import annotations

import logging
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from data import cache as cache_module
from data.freshness_store import get_freshness_flag, get_freshness_meta
from data.portfolio_store import get_current_holdings, get_latest_decision, get_latest_portfolio_snapshot, get_or_create_account
from integrations.robinhood.snaptrade_client import SnapTradeClient
from models.schemas import Bucket, DataFreshnessStatus, DashboardFreshnessSummary
from services.scan_manager import scan_manager

logger = logging.getLogger(__name__)

NY_TZ = ZoneInfo("America/New_York")

# Default TTL seconds by key (overridden by market session for some keys)
DEFAULT_STALE_AFTER: dict[str, int] = {
    "portfolio_holdings": 1800,
    "latest_prices": 300,
    "daily_decision": 86400,
    "penny_scan": 1800,
    "compounder_scan": 86400,
    "risk_metrics": 86400,
    "data_quality": 86400,
    "closed_positions": 86400,
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _parse_ts(value: str | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None) if value.tzinfo else value
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
        return dt.replace(tzinfo=None) if dt.tzinfo else dt
    except ValueError:
        return None


def _age_seconds(ts: datetime | None) -> float | None:
    if ts is None:
        return None
    return max(0.0, (_utcnow() - ts).total_seconds())


def _is_trading_day(dt: datetime | None = None) -> bool:
    from services.scheduler import _is_trading_session

    return _is_trading_session()


def get_market_session_band(now: datetime | None = None) -> str:
    """
    Returns one of: regular | extended | closed_hours | closed_day
    - regular: Mon-Fri trading day 9:30–16:00 ET
    - extended: trading day 4:00–9:30 or 16:00–20:00 ET
    - closed_hours: trading day outside extended window
    - closed_day: non-trading day
    """
    if not _is_trading_day():
        return "closed_day"
    now_et = (now or _utcnow()).replace(tzinfo=timezone.utc).astimezone(NY_TZ)
    t = now_et.time()
    if time(9, 30) <= t < time(16, 0):
        return "regular"
    if time(4, 0) <= t < time(9, 30) or time(16, 0) <= t < time(20, 0):
        return "extended"
    return "closed_hours"


def price_stale_after_seconds() -> int:
    band = get_market_session_band()
    if band == "regular":
        return 300
    if band == "extended":
        return 1800
    return 86400


def penny_stale_after_seconds() -> int:
    band = get_market_session_band()
    if band == "regular":
        return 1800
    return 86400


def _last_trading_session_open(now: datetime | None = None) -> datetime:
    """9:00 AM ET on the current or most recent trading session."""
    now_et = (now or _utcnow()).replace(tzinfo=timezone.utc).astimezone(NY_TZ)
    try:
        import exchange_calendars as xcals
        import pandas as pd

        from config import SCHEDULER_MARKET_CALENDAR

        cal = xcals.get_calendar(SCHEDULER_MARKET_CALENDAR)
        today = pd.Timestamp(now_et.date(), tz=NY_TZ)
        if cal.is_session(today):
            session_date = today
        else:
            session_date = cal.previous_session(today)
        return datetime.combine(session_date.date(), time(9, 0), tzinfo=NY_TZ).replace(tzinfo=None)
    except Exception:
        # Fallback: today 9 AM ET if weekday else last weekday
        d = now_et.date()
        while d.weekday() >= 5:
            d -= timedelta(days=1)
        return datetime.combine(d, time(9, 0), tzinfo=NY_TZ).replace(tzinfo=None)


def _decision_trading_day(decision_ts: datetime) -> datetime | None:
    """Date (as naive ET midnight) of the trading session the decision belongs to."""
    try:
        import exchange_calendars as xcals
        import pandas as pd

        from config import SCHEDULER_MARKET_CALENDAR

        cal = xcals.get_calendar(SCHEDULER_MARKET_CALENDAR)
        ts_et = decision_ts.replace(tzinfo=timezone.utc).astimezone(NY_TZ)
        day = pd.Timestamp(ts_et.date(), tz=NY_TZ)
        if cal.is_session(day):
            return datetime.combine(day.date(), time(0, 0))
        prev = cal.previous_session(day)
        return datetime.combine(prev.date(), time(0, 0))
    except Exception:
        d = decision_ts.date()
        while d.weekday() >= 5:
            d -= timedelta(days=1)
        return datetime.combine(d, time(0, 0))


def _latest_price_refresh_ts(symbols: list[str]) -> datetime | None:
    meta = get_freshness_meta("latest_prices")
    meta_ts = _parse_ts(meta.get("last_updated_at") if meta else None)
    if not symbols:
        return meta_ts
    try:
        from data.historical_store import HistoricalStore, DailyQuote, SessionLocal

        session = SessionLocal()
        try:
            row = (
                session.query(DailyQuote.updated_at)
                .filter(DailyQuote.symbol.in_([s.upper() for s in symbols]))
                .order_by(DailyQuote.updated_at.desc())
                .first()
            )
            quote_ts = row[0] if row else None
        finally:
            session.close()
    except Exception as exc:
        logger.debug("Quote freshness lookup skipped: %s", exc)
        quote_ts = None
    candidates = [t for t in (meta_ts, quote_ts) if t]
    return max(candidates) if candidates else None


def _scan_completed_at(bucket: str) -> datetime | None:
    data = scan_manager.get_latest_scan(Bucket(bucket))
    if not data:
        saved = cache_module.list_saved_scans(bucket=bucket, limit=1)
        if saved:
            return _parse_ts(saved[0].get("completed_at") or saved[0].get("created_at"))
        return None
    return _parse_ts(data.get("completed_at"))


def _status(
    key: str,
    *,
    last_updated_at: datetime | None,
    stale_after: int,
    is_missing: bool = False,
    reason: str = "",
    source: str = "system",
) -> DataFreshnessStatus:
    age = _age_seconds(last_updated_at)
    is_stale = is_missing or (age is not None and age > stale_after) or (last_updated_at is None and not is_missing)
    if last_updated_at is None and not is_missing:
        is_stale = True
        if not reason:
            reason = "No refresh timestamp recorded"
    elif age is not None and age > stale_after and not reason:
        reason = f"Last updated {int(age)}s ago (TTL {stale_after}s)"
    return DataFreshnessStatus(
        key=key,
        last_updated_at=last_updated_at.isoformat() + "Z" if last_updated_at else None,
        stale_after_seconds=stale_after,
        is_stale=is_stale,
        is_missing=is_missing,
        reason=reason,
        source=source,
    )


def assess_portfolio_holdings() -> DataFreshnessStatus:
    holdings = get_current_holdings()
    account = get_or_create_account()
    snap = get_latest_portfolio_snapshot()
    last_ts = _parse_ts((snap or {}).get("created_at"))
    if account.get("last_sync_at"):
        sync_ts = _parse_ts(account["last_sync_at"])
        if sync_ts and (last_ts is None or sync_ts > last_ts):
            last_ts = sync_ts

    meta = get_freshness_meta("portfolio_holdings")
    if meta and meta.get("last_updated_at"):
        meta_ts = _parse_ts(meta["last_updated_at"])
        if meta_ts and (last_ts is None or meta_ts > last_ts):
            last_ts = meta_ts

    if not holdings:
        return _status(
            "portfolio_holdings",
            last_updated_at=last_ts,
            stale_after=DEFAULT_STALE_AFTER["portfolio_holdings"],
            is_missing=True,
            reason="No holdings — import Robinhood CSV",
            source=account.get("source", "manual"),
        )

    if get_freshness_flag("portfolio_holdings", "holdings_dirty"):
        return _status(
            "portfolio_holdings",
            last_updated_at=last_ts,
            stale_after=0,
            reason="Holdings changed after last refresh (CSV import or sync)",
            source=account.get("source", "manual"),
        )

    stale_after = DEFAULT_STALE_AFTER["portfolio_holdings"]
    reason = ""
    client = SnapTradeClient()
    if client.is_configured():
        band = get_market_session_band()
        if band in ("regular", "extended"):
            stale_after = 1800
            age = _age_seconds(_parse_ts(account.get("last_sync_at")))
            if age is not None and age > stale_after:
                reason = f"Brokerage sync older than {stale_after // 60} min during market hours"

    return _status(
        "portfolio_holdings",
        last_updated_at=last_ts,
        stale_after=stale_after,
        reason=reason,
        source=account.get("source", "manual"),
    )


def assess_latest_prices() -> DataFreshnessStatus:
    symbols = [h["symbol"] for h in get_current_holdings()]
    last_ts = _latest_price_refresh_ts(symbols)
    stale_after = price_stale_after_seconds()
    reason = ""
    if not symbols:
        return _status(
            "latest_prices",
            last_updated_at=last_ts,
            stale_after=stale_after,
            is_missing=True,
            reason="No holdings to price",
        )
    return _status("latest_prices", last_updated_at=last_ts, stale_after=stale_after, reason=reason, source="price_service")


def assess_daily_decision() -> DataFreshnessStatus:
    latest = get_latest_decision()
    snap = get_latest_portfolio_snapshot()
    holdings = get_current_holdings()
    symbols = [h["symbol"] for h in holdings]

    if not latest:
        return _status(
            "daily_decision",
            last_updated_at=None,
            stale_after=DEFAULT_STALE_AFTER["daily_decision"],
            is_missing=True,
            reason="No decision snapshot exists",
        )

    decision_ts = _parse_ts(latest.get("created_at"))
    stale_after = DEFAULT_STALE_AFTER["daily_decision"]
    reason = ""

    snap_ts = _parse_ts((snap or {}).get("created_at"))
    if snap_ts and decision_ts and snap_ts > decision_ts:
        return _status(
            "daily_decision",
            last_updated_at=decision_ts,
            stale_after=0,
            reason="Holdings changed after last decision",
            source=latest.get("trigger", "unknown"),
        )

    price_ts = _latest_price_refresh_ts(symbols)
    if price_ts and decision_ts and price_ts > decision_ts:
        return _status(
            "daily_decision",
            last_updated_at=decision_ts,
            stale_after=0,
            reason="Prices refreshed after last decision",
            source=latest.get("trigger", "unknown"),
        )

    session_open = _last_trading_session_open()
    if decision_ts and decision_ts < session_open and _is_trading_day():
        return _status(
            "daily_decision",
            last_updated_at=decision_ts,
            stale_after=0,
            reason="Decision predates today's 9:00 AM ET session open",
            source=latest.get("trigger", "unknown"),
        )

    decision_day = _decision_trading_day(decision_ts) if decision_ts else None
    today_open = _last_trading_session_open()
    if decision_day and decision_day.date() < today_open.date():
        return _status(
            "daily_decision",
            last_updated_at=decision_ts,
            stale_after=0,
            reason="Decision was generated on a previous trading day",
            source=latest.get("trigger", "unknown"),
        )

    return _status(
        "daily_decision",
        last_updated_at=decision_ts,
        stale_after=stale_after,
        reason=reason,
        source=latest.get("trigger", "unknown"),
    )


def assess_penny_scan() -> DataFreshnessStatus:
    completed = _scan_completed_at("penny")
    stale_after = penny_stale_after_seconds()
    if completed is None:
        return _status(
            "penny_scan",
            last_updated_at=None,
            stale_after=stale_after,
            is_missing=True,
            reason="No penny scan results cached",
            source="scan_manager",
        )
    return _status("penny_scan", last_updated_at=completed, stale_after=stale_after, source="scan_manager")


def assess_compounder_scan() -> DataFreshnessStatus:
    completed = _scan_completed_at("compounder")
    stale_after = DEFAULT_STALE_AFTER["compounder_scan"]
    if completed is None:
        return _status(
            "compounder_scan",
            last_updated_at=None,
            stale_after=stale_after,
            is_missing=True,
            reason="No compounder scan results cached",
            source="scan_manager",
        )
    return _status("compounder_scan", last_updated_at=completed, stale_after=stale_after, source="scan_manager")


def assess_risk_metrics() -> DataFreshnessStatus:
    meta = get_freshness_meta("risk_metrics")
    last_ts = _parse_ts(meta.get("last_updated_at") if meta else None)
    latest = get_latest_decision()
    if last_ts is None and latest:
        last_ts = _parse_ts(latest.get("created_at"))
    return _status(
        "risk_metrics",
        last_updated_at=last_ts,
        stale_after=DEFAULT_STALE_AFTER["risk_metrics"],
        source=(meta or {}).get("source", "decision"),
    )


def assess_data_quality() -> DataFreshnessStatus:
    meta = get_freshness_meta("data_quality")
    last_ts = _parse_ts(meta.get("last_updated_at") if meta else None)
    latest = get_latest_decision()
    if last_ts is None and latest:
        last_ts = _parse_ts(latest.get("created_at"))
    return _status(
        "data_quality",
        last_updated_at=last_ts,
        stale_after=DEFAULT_STALE_AFTER["data_quality"],
        source=(meta or {}).get("source", "decision"),
    )


def assess_closed_positions() -> DataFreshnessStatus:
    snap = get_latest_portfolio_snapshot()
    account = get_or_create_account()
    last_ts = _parse_ts((snap or {}).get("created_at"))
    meta = get_freshness_meta("closed_positions")
    if meta and meta.get("last_updated_at"):
        meta_ts = _parse_ts(meta["last_updated_at"])
        if meta_ts:
            last_ts = meta_ts

    reason = ""
    if get_freshness_flag("closed_positions", "needs_refresh"):
        reason = "Trade history import or brokerage sync pending closed-position refresh"

    sync_ts = _parse_ts(account.get("last_sync_at"))
    if sync_ts and last_ts and sync_ts > last_ts:
        reason = reason or "Brokerage sync newer than closed positions snapshot"

    return _status(
        "closed_positions",
        last_updated_at=last_ts,
        stale_after=0 if reason else DEFAULT_STALE_AFTER["closed_positions"],
        reason=reason,
        source=account.get("source", "manual"),
    )


def assess_freshness(key: str) -> DataFreshnessStatus:
    assessors = {
        "portfolio_holdings": assess_portfolio_holdings,
        "latest_prices": assess_latest_prices,
        "daily_decision": assess_daily_decision,
        "penny_scan": assess_penny_scan,
        "compounder_scan": assess_compounder_scan,
        "risk_metrics": assess_risk_metrics,
        "data_quality": assess_data_quality,
        "closed_positions": assess_closed_positions,
    }
    fn = assessors.get(key)
    if not fn:
        raise ValueError(f"Unknown freshness key: {key}")
    return fn()


# Keys that drive home cockpit overall status and auto-refresh (not compounder / ancillary).
HOME_COCKPIT_FRESHNESS_KEYS = (
    "portfolio_holdings",
    "latest_prices",
    "daily_decision",
    "penny_scan",
)


def assess_all_freshness(*, refresh_in_progress: bool = False, refresh_job_id: str | None = None) -> DashboardFreshnessSummary:
    account = get_or_create_account()
    items = [
        assess_portfolio_holdings(),
        assess_latest_prices(),
        assess_daily_decision(),
        assess_penny_scan(),
        assess_compounder_scan(),
        assess_risk_metrics(),
        assess_data_quality(),
        assess_closed_positions(),
    ]

    home_items = [i for i in items if i.key in HOME_COCKPIT_FRESHNESS_KEYS]

    if account.get("source") == "demo":
        overall = "demo"
    elif refresh_in_progress:
        overall = "updating"
    elif any(i.is_missing for i in home_items if i.key in ("portfolio_holdings", "daily_decision")):
        overall = "missing"
    elif any(i.is_stale for i in home_items):
        overall = "stale"
    else:
        overall = "fresh"

    prices = next(i for i in items if i.key == "latest_prices")
    penny = next(i for i in items if i.key == "penny_scan")
    holdings = next(i for i in items if i.key == "portfolio_holdings")
    decision = next(i for i in items if i.key == "daily_decision")

    refresh_recommended = (
        not refresh_in_progress
        and overall in ("stale", "missing")
        and account.get("source") != "demo"
        and any(i.is_stale or i.is_missing for i in home_items)
    )

    return DashboardFreshnessSummary(
        overall_status=overall,
        items=items,
        refresh_recommended=refresh_recommended,
        refresh_in_progress=refresh_in_progress,
        refresh_job_id=refresh_job_id,
        last_holdings_sync_at=holdings.last_updated_at,
        last_price_update_at=prices.last_updated_at,
        last_decision_run_at=decision.last_updated_at,
        last_penny_scan_at=penny.last_updated_at,
    )


def is_symbol_price_stale(symbol: str) -> bool:
    status = assess_latest_prices()
    if status.is_missing:
        return True
    try:
        from data.historical_store import DailyQuote, SessionLocal

        session = SessionLocal()
        try:
            row = (
                session.query(DailyQuote.updated_at)
                .filter(DailyQuote.symbol == symbol.upper())
                .order_by(DailyQuote.updated_at.desc())
                .first()
            )
            ts = row[0] if row else None
        finally:
            session.close()
    except Exception:
        ts = _parse_ts(status.last_updated_at)
    stale_after = price_stale_after_seconds()
    age = _age_seconds(ts)
    return ts is None or (age is not None and age > stale_after)
