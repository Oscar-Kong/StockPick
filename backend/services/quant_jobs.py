"""Scheduled quant v2 jobs — regime, IC panel, weight rebalance."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from config import QUANT_JOBS_ENABLED
from data.historical_store import HistoricalStore

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _is_first_trading_day_of_month() -> bool:
    try:
        import exchange_calendars as xcals
        import pandas as pd
        from config import SCHEDULER_MARKET_CALENDAR, SCHEDULER_TZ

        cal = xcals.get_calendar(SCHEDULER_MARKET_CALENDAR)
        now = pd.Timestamp.now(tz=SCHEDULER_TZ).normalize()
        month_sessions = cal.sessions_in_range(
            now.replace(day=1),
            now + pd.Timedelta(days=1),
        )
        if len(month_sessions) == 0:
            return False
        return month_sessions[0] == now.tz_convert(month_sessions.tz)
    except Exception:
        return datetime.now(timezone.utc).day <= 3


def run_daily_quant_jobs(*, force_rebalance: bool = False) -> dict:
    """Regime update, IC panel, optional monthly weight rebalance."""
    if not QUANT_JOBS_ENABLED:
        return {"skipped": True, "reason": "QUANT_JOBS_ENABLED=false"}

    store = HistoricalStore()
    started = _utcnow()
    summary: dict = {"regime": None, "ic_panel": None, "rebalance": None}

    try:
        from engines.weighting.regime_classifier import classify_spy
        from engines.weighting.weight_store import WeightStore

        result = classify_spy()
        if result:
            WeightStore.persist_regime(result)
            summary["regime"] = result.regime
    except Exception as exc:
        logger.warning("Regime job failed: %s", exc)
        summary["regime_error"] = str(exc)

    try:
        from engines.weighting.ic_panel import run_ic_panel

        summary["ic_panel"] = run_ic_panel()
    except Exception as exc:
        logger.warning("IC panel job failed: %s", exc)
        summary["ic_panel_error"] = str(exc)

    if force_rebalance or _is_first_trading_day_of_month():
        try:
            from engines.weighting.weight_store import WeightStore

            summary["rebalance"] = WeightStore.rebalance_all_sleeves(smooth=True)
        except Exception as exc:
            logger.warning("Weight rebalance failed: %s", exc)
            summary["rebalance_error"] = str(exc)

        try:
            from engines.feedback.learning import run_trade_feedback_learning

            summary["trade_feedback"] = run_trade_feedback_learning()
        except Exception as exc:
            logger.warning("Trade feedback learning failed: %s", exc)
            summary["trade_feedback_error"] = str(exc)

    try:
        from engines.prediction.snapshots import resolve_prediction_outcomes

        summary["prediction_outcomes"] = resolve_prediction_outcomes()
    except Exception as exc:
        logger.warning("Prediction outcome resolution failed: %s", exc)
        summary["prediction_outcomes_error"] = str(exc)

    try:
        from config import FORWARD_LABELS_ENABLED

        if FORWARD_LABELS_ENABLED:
            from engines.labels.forward_returns import build_forward_labels

            summary["forward_labels"] = build_forward_labels()
    except Exception as exc:
        logger.warning("Forward labels job failed: %s", exc)
        summary["forward_labels_error"] = str(exc)

    try:
        from engines.feedback.outcome_weights import run_outcome_weight_feedback

        summary["outcome_weight_feedback"] = run_outcome_weight_feedback()
    except Exception as exc:
        logger.warning("Outcome weight feedback failed: %s", exc)
        summary["outcome_weight_feedback_error"] = str(exc)

    try:
        from config import PIT_FUNDAMENTALS_ENABLED

        if PIT_FUNDAMENTALS_ENABLED:
            from data.pit_fmp_ingest import build_pit_panel

            summary["pit_fundamentals"] = build_pit_panel()
    except Exception as exc:
        logger.warning("PIT fundamentals job failed: %s", exc)
        summary["pit_fundamentals_error"] = str(exc)

    status = "ok" if not any(k.endswith("_error") for k in summary) else "partial"
    store.log_job(
        "quant_daily_jobs",
        status,
        f"regime={summary.get('regime')} ic={summary.get('ic_panel', {}).get('factors_computed')}",
        symbols_processed=summary.get("ic_panel", {}).get("factors_computed") or 0,
        errors=0,
        started_at=started,
        finished_at=_utcnow(),
    )
    summary["status"] = status
    from engines.audit.logger import audit_log

    audit_log("quant_daily_jobs", payload=summary)
    return summary
