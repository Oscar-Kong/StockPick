"""Home dashboard polling should not re-trigger background refresh."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from api.routes_home import daily_dashboard


def test_daily_dashboard_skip_auto_refresh():
    dashboard = MagicMock()
    dashboard.freshness = MagicMock()
    with patch("api.routes_home.build_daily_dashboard", return_value=dashboard) as build:
        with patch("api.routes_home._attach_auto_refresh") as attach:
            result = daily_dashboard(skip_auto_refresh=True)
    build.assert_called_once_with(include_freshness=True)
    attach.assert_not_called()
    assert result is dashboard
