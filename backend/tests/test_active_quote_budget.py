from unittest.mock import patch

from services.refresh_orchestrator import PortfolioRefresh


def test_active_quote_refresh_is_penny_only_and_honors_daily_budget():
    holdings = [
        {"symbol": "PENNY", "bucket": "penny"},
        {"symbol": "OTHER", "bucket": "penny"},
        {"symbol": "LONG", "bucket": "compounder"},
    ]
    refresh = PortfolioRefresh()

    with (
        patch("services.refresh_orchestrator.get_current_holdings", return_value=holdings),
        patch("config.ACTIVE_POSITION_MAX_SYMBOLS_PER_REFRESH", 10),
        patch("config.ACTIVE_POSITION_DAILY_REQUEST_BUDGET", 1),
        patch(
            "services.refresh_orchestrator.PriceService.refresh_latest_quote",
            return_value=2.5,
        ) as quote,
    ):
        first = refresh.refresh_active_quotes()
        second = refresh.refresh_active_quotes()

    assert first["provider_requests"] == 1
    assert first["daily_budget_remaining"] == 0
    assert first["deferred"] == ["OTHER"]
    assert second["provider_requests"] == 0
    assert quote.call_count == 1
