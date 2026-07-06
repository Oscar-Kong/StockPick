"""PortfolioRefresh scheduled job routing."""
from __future__ import annotations

from unittest.mock import patch

from services.portfolio_jobs import run_scheduled_portfolio_decision


def test_scheduled_decision_uses_decision_chain():
    with patch("services.scheduler._is_trading_session", return_value=True):
        with patch("services.refresh_orchestrator.portfolio_refresh.refresh") as refresh:
            refresh.return_value = {"status": "ok", "steps": {}}
            with patch("services.portfolio_jobs.PORTFOLIO_DECISION_ENABLED", True):
                result = run_scheduled_portfolio_decision()
    refresh.assert_called_once_with("decision_chain", trigger="scheduled", force=False)
    assert result["status"] == "ok"
