"""Scheduled portfolio jobs — thin adapters over PortfolioRefresh."""
from __future__ import annotations

import logging

from config import PORTFOLIO_DECISION_ENABLED

logger = logging.getLogger(__name__)


def run_scheduled_portfolio_decision() -> dict:
    if not PORTFOLIO_DECISION_ENABLED:
        return {"skipped": True, "reason": "PORTFOLIO_DECISION_ENABLED=false"}

    from services.scheduler import _is_trading_session

    if not _is_trading_session():
        logger.info("Skipping portfolio decision — not a trading session")
        return {"skipped": True, "reason": "non_trading_day"}

    from services.refresh_orchestrator import portfolio_refresh

    return portfolio_refresh.refresh("decision_chain", trigger="scheduled", force=False)


def run_market_data_price_refresh() -> dict:
    from config import MARKET_DATA_REFRESH_ENABLED
    from services.data_freshness_service import get_market_session_band

    if not MARKET_DATA_REFRESH_ENABLED:
        return {"skipped": True, "reason": "MARKET_DATA_REFRESH_ENABLED=false"}

    if get_market_session_band() != "regular":
        return {"skipped": True, "reason": "outside_regular_market_hours"}

    from services.refresh_orchestrator import portfolio_refresh

    return portfolio_refresh.refresh("prices", trigger="scheduled", force=False)


def run_scheduled_penny_scan_refresh() -> dict:
    from config import MARKET_DATA_REFRESH_ENABLED
    from services.data_freshness_service import get_market_session_band

    if not MARKET_DATA_REFRESH_ENABLED:
        return {"skipped": True, "reason": "MARKET_DATA_REFRESH_ENABLED=false"}

    if get_market_session_band() != "regular":
        return {"skipped": True, "reason": "outside_regular_market_hours"}

    from services.refresh_orchestrator import portfolio_refresh

    return portfolio_refresh.refresh("penny_scan", trigger="scheduled", force=False)
