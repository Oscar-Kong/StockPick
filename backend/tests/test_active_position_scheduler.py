from __future__ import annotations

from unittest.mock import patch

from services.scheduler import _scheduled_active_monitor, _scheduled_active_quote_refresh


def test_active_quote_scheduler_uses_quote_only_refresh():
    with (
        patch("services.scheduler._is_trading_session", return_value=True),
        patch("services.scheduler._is_regular_market_time", return_value=True),
        patch(
            "services.active_position_monitor_service.refresh_and_store_active_quotes",
            return_value={"quote_only": True, "refreshed": 2},
        ) as refresh,
    ):
        result = _scheduled_active_quote_refresh()

    assert result["quote_only"] is True
    refresh.assert_called_once_with()


def test_active_monitor_scheduler_evaluates_cached_quotes_without_refetch():
    with (
        patch("services.scheduler._is_trading_session", return_value=True),
        patch("services.scheduler._is_regular_market_time", return_value=True),
        patch(
            "services.active_position_monitor_service.run_active_position_monitor",
            return_value={"statuses": [], "quote_only": True},
        ) as run,
    ):
        result = _scheduled_active_monitor()

    assert result["quote_only"] is True
    run.assert_called_once_with(refresh_quotes=False)
