"""Scheduled daily data refresh jobs with error logging."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from data.historical_store import HistoricalStore
from data.price_service import PriceService
from data.reconciler import DataReconciler
from data.universe import get_universe

logger = logging.getLogger(__name__)

_scheduler = None


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def refresh_universe_quotes(symbols: list[str] | None = None, period: str = "1y") -> dict:
    """Download and persist adjusted OHLC for universe symbols."""
    store = HistoricalStore()
    ps = PriceService()
    started = _utcnow()
    symbols = symbols or _collect_all_symbols()
    processed = 0
    errors = 0

    for sym in symbols:
        try:
            df = ps.get_history(sym, period=period)
            if df.empty:
                errors += 1
                store.add_quality_flag(sym, "missing_data", f"No OHLC returned for {period}")
                continue
            rows = df.to_dict("records")
            for r in rows:
                r["date"] = str(r["date"])[:10]
            store.upsert_quotes(sym, rows)
            processed += 1
        except Exception as exc:
            errors += 1
            logger.warning("Quote refresh failed for %s: %s", sym, exc)
            store.add_quality_flag(sym, "refresh_error", str(exc)[:200])

    status = "ok" if errors == 0 else ("partial" if processed else "failed")
    store.log_job(
        "daily_quote_refresh",
        status,
        f"Processed {processed}, errors {errors}",
        symbols_processed=processed,
        errors=errors,
        started_at=started,
        finished_at=_utcnow(),
    )
    return {"status": status, "processed": processed, "errors": errors}


def refresh_fundamentals(symbols: list[str] | None = None, limit: int = 50) -> dict:
    """Reconcile and persist fundamentals for top symbols."""
    store = HistoricalStore()
    reconciler = DataReconciler()
    started = _utcnow()
    symbols = (symbols or _collect_all_symbols())[:limit]
    processed = 0
    errors = 0

    for sym in symbols:
        try:
            info, fundamentals, rec = reconciler.get_canonical_fundamentals(sym)
            if not info and not fundamentals:
                errors += 1
                continue
            payload = {"info": info, "fundamentals": fundamentals, "reconcile": rec.to_dict()}
            store.save_fundamentals(sym, payload, source="reconciled", quality_score=rec.quality_score)
            for flag in rec.flags:
                store.add_quality_flag(sym, "reconcile", flag)
            processed += 1
        except Exception as exc:
            errors += 1
            logger.warning("Fundamentals refresh failed for %s: %s", sym, exc)

    status = "ok" if errors == 0 else ("partial" if processed else "failed")
    store.log_job(
        "daily_fundamentals_refresh",
        status,
        f"Processed {processed}, errors {errors}",
        symbols_processed=processed,
        errors=errors,
        started_at=started,
        finished_at=_utcnow(),
    )
    return {"status": status, "processed": processed, "errors": errors}


def run_daily_pipeline() -> dict:
    """Full daily update: quotes then fundamentals."""
    quote_result = refresh_universe_quotes()
    fund_result = refresh_fundamentals(limit=50)
    return {"quotes": quote_result, "fundamentals": fund_result}


def _collect_all_symbols() -> list[str]:
    from buckets import ACTIVE_BUCKETS

    seen: set[str] = set()
    for bucket in ACTIVE_BUCKETS:
        for s in get_universe(bucket):
            seen.add(s.upper())
    return sorted(seen)


def _is_trading_session() -> bool:
    """Optional NYSE session check when exchange_calendars is installed."""
    from config import SCHEDULER_MARKET_CALENDAR, SCHEDULER_TZ

    try:
        import exchange_calendars as xcals
        import pandas as pd

        cal = xcals.get_calendar(SCHEDULER_MARKET_CALENDAR)
        today = pd.Timestamp.now(tz=SCHEDULER_TZ).normalize()
        return bool(cal.is_session(today))
    except ImportError:
        return True
    except Exception as exc:
        logger.debug("Market calendar check skipped: %s", exc)
        return True


def _scheduled_pipeline() -> dict:
    if not _is_trading_session():
        logger.info("Skipping daily pipeline — not a trading session")
        return {"skipped": True, "reason": "non_trading_day"}
    from engines.jobs.queue import dispatch_job

    return dispatch_job("daily_pipeline", {})


def _scheduled_quant_jobs() -> dict:
    if not _is_trading_session():
        logger.info("Skipping quant jobs — not a trading session")
        return {"skipped": True, "reason": "non_trading_day"}
    from engines.jobs.queue import dispatch_job

    return dispatch_job("quant_daily_jobs", {})


def _scheduled_portfolio_decision() -> dict:
    if not _is_trading_session():
        logger.info("Skipping portfolio decision — not a trading session")
        return {"skipped": True, "reason": "non_trading_day"}
    from engines.jobs.queue import dispatch_job

    return dispatch_job("daily_portfolio_decision", {})


def start_scheduler() -> None:
    """Start APScheduler for daily jobs if SCHEDULER_ENABLED."""
    global _scheduler
    from config import (
        PORTFOLIO_DECISION_CRON,
        PORTFOLIO_DECISION_ENABLED,
        PORTFOLIO_DECISION_TZ,
        SCHEDULER_CRON,
        SCHEDULER_ENABLED,
        SCHEDULER_TZ,
    )

    if not SCHEDULER_ENABLED:
        logger.info("Scheduler disabled (SCHEDULER_ENABLED=false)")
        return

    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger
    except ImportError:
        logger.warning("APScheduler not installed; daily jobs disabled")
        return

    if _scheduler is not None:
        return

    _scheduler = BackgroundScheduler(timezone=SCHEDULER_TZ)
    _scheduler.add_job(
        _scheduled_pipeline,
        CronTrigger.from_crontab(SCHEDULER_CRON, timezone=SCHEDULER_TZ),
        id="daily_pipeline",
        replace_existing=True,
    )
    from config import QUANT_IC_CRON, QUANT_JOBS_ENABLED

    if QUANT_JOBS_ENABLED:
        _scheduler.add_job(
            _scheduled_quant_jobs,
            CronTrigger.from_crontab(QUANT_IC_CRON, timezone=SCHEDULER_TZ),
            id="quant_daily_jobs",
            replace_existing=True,
        )
    if PORTFOLIO_DECISION_ENABLED:
        _scheduler.add_job(
            _scheduled_portfolio_decision,
            CronTrigger.from_crontab(PORTFOLIO_DECISION_CRON, timezone=PORTFOLIO_DECISION_TZ),
            id="daily_portfolio_decision",
            replace_existing=True,
        )
    _scheduler.start()
    logger.info(
        "Scheduler started — pipeline '%s' (%s); portfolio decision '%s' (%s)",
        SCHEDULER_CRON,
        SCHEDULER_TZ,
        PORTFOLIO_DECISION_CRON if PORTFOLIO_DECISION_ENABLED else "off",
        PORTFOLIO_DECISION_TZ,
    )


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
