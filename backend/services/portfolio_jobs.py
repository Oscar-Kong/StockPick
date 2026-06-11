"""Scheduled portfolio decision job."""
from __future__ import annotations

import logging

from config import PORTFOLIO_DECISION_ENABLED
from data.portfolio_store import get_current_holdings
from data.price_service import PriceService
from services.portfolio_decision_service import run_stored_portfolio_decision
from services.portfolio_snapshot_service import refresh_holdings_snapshot, sync_brokerage_if_configured

logger = logging.getLogger(__name__)


def run_scheduled_portfolio_decision() -> dict:
    if not PORTFOLIO_DECISION_ENABLED:
        return {"skipped": True, "reason": "PORTFOLIO_DECISION_ENABLED=false"}

    from services.scheduler import _is_trading_session

    if not _is_trading_session():
        logger.info("Skipping portfolio decision — not a trading session")
        return {"skipped": True, "reason": "non_trading_day"}

    sync_result = sync_brokerage_if_configured()
    refresh_holdings_snapshot()

    holdings = get_current_holdings()
    if not holdings:
        return {"skipped": True, "reason": "no_holdings", "sync": sync_result}

    ps = PriceService()
    for h in holdings:
        try:
            ps.get_history(h["symbol"], period="5d")
        except Exception as exc:
            logger.debug("Quote refresh skipped for %s: %s", h["symbol"], exc)

    try:
        decision = run_stored_portfolio_decision(trigger="scheduled", persist=True)
        from data.freshness_store import mark_freshness_updated

        mark_freshness_updated("daily_decision", source="scheduled")
        mark_freshness_updated("latest_prices", source="scheduled")
        return {
            "status": "ok",
            "holdings": len(holdings),
            "items": len(decision.items),
            "sync": sync_result,
        }
    except Exception as exc:
        logger.warning("Scheduled portfolio decision failed: %s", exc)
        return {"status": "failed", "error": str(exc)[:200]}


def run_market_data_price_refresh() -> dict:
    from config import MARKET_DATA_REFRESH_ENABLED
    from services.data_freshness_service import get_market_session_band

    if not MARKET_DATA_REFRESH_ENABLED:
        return {"skipped": True, "reason": "MARKET_DATA_REFRESH_ENABLED=false"}

    if get_market_session_band() != "regular":
        return {"skipped": True, "reason": "outside_regular_market_hours"}

    from services.refresh_orchestrator import refresh_prices_for_holdings

    return refresh_prices_for_holdings(force=False)


def run_scheduled_penny_scan_refresh() -> dict:
    from config import MARKET_DATA_REFRESH_ENABLED
    from services.data_freshness_service import get_market_session_band

    if not MARKET_DATA_REFRESH_ENABLED:
        return {"skipped": True, "reason": "MARKET_DATA_REFRESH_ENABLED=false"}

    if get_market_session_band() != "regular":
        return {"skipped": True, "reason": "outside_regular_market_hours"}

    from services.refresh_orchestrator import refresh_penny_scan_if_needed

    return refresh_penny_scan_if_needed(force=False)
