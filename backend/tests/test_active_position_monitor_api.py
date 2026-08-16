from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from main import app


def test_active_monitor_api_exposes_read_only_status():
    payload = {
        "as_of": "2026-08-16T14:30:00Z",
        "statuses": [
            {
                "symbol": "TEST",
                "bucket": "penny",
                "state": "HOLD",
                "actionable": False,
                "price": 10.2,
                "quote_as_of": "2026-08-16T14:30:00Z",
                "quote_age_seconds": 10,
                "data_status": "fresh",
                "shares": 10,
                "avg_cost": 10,
                "unrealized_pl_pct": 2,
                "stop_price": 9.5,
                "target_price": 11,
                "distance_to_stop_pct": 7.37,
                "distance_to_target_pct": 7.84,
                "evidence": ["No configured state boundary crossed"],
                "updated_at": "2026-08-16T14:30:00Z",
            }
        ],
        "transitions": [],
        "execution_enabled": False,
    }
    with patch("api.routes_portfolio.get_active_position_monitor_status", return_value=payload):
        response = TestClient(app).get("/portfolio/active-monitor")

    assert response.status_code == 200
    body = response.json()
    assert body["statuses"][0]["state"] == "HOLD"
    assert body["execution_enabled"] is False


def test_active_monitor_run_can_refresh_quotes_without_enabling_execution():
    payload = {
        "as_of": "2026-08-16T14:30:00Z",
        "quote_as_of": "2026-08-16T14:30:00Z",
        "statuses": [],
        "transitions": [],
        "notifications": [],
        "quote_only": True,
        "execution_enabled": False,
    }
    with patch("api.routes_portfolio.run_active_position_monitor", return_value=payload) as run:
        response = TestClient(app).post("/portfolio/active-monitor/run?refresh_quotes=true")

    assert response.status_code == 200
    assert response.json()["execution_enabled"] is False
    run.assert_called_once_with(refresh_quotes=True)
