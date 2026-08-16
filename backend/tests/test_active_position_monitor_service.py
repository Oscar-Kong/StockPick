from __future__ import annotations

from unittest.mock import patch

from services.active_position_monitor_service import (
    _select_notifications,
    refresh_and_store_active_quotes,
    run_active_position_monitor,
)


def test_quote_refresh_persists_timestamped_quote_snapshot():
    with (
        patch(
            "services.active_position_monitor_service.refresh_active_quotes",
            return_value={"quotes": {"TEST": 10.25}, "quote_only": True},
        ),
        patch("services.active_position_monitor_service.save_active_quote_snapshot") as save,
    ):
        result = refresh_and_store_active_quotes()

    assert result["quote_only"] is True
    save.assert_called_once()
    assert save.call_args.args[0] == {"TEST": 10.25}
    assert save.call_args.kwargs["as_of"]


def test_monitor_uses_cached_quotes_and_persists_only_changed_states():
    holdings = [{"symbol": "TEST", "shares": 10, "avg_cost": 10.0, "bucket": "penny"}]
    quote_snapshot = {
        "as_of": "2026-08-16T14:30:00+00:00",
        "quotes": {"TEST": {"price": 10.2, "as_of": "2026-08-16T14:30:00+00:00"}},
    }
    with (
        patch("services.active_position_monitor_service.get_current_holdings", return_value=holdings),
        patch(
            "services.active_position_monitor_service.get_active_quote_snapshot",
            return_value=quote_snapshot,
        ),
        patch("services.active_position_monitor_service.get_active_position_states", return_value=[]),
        patch("services.active_position_monitor_service.save_active_position_monitor_result") as save,
    ):
        result = run_active_position_monitor(now="2026-08-16T14:30:30+00:00")

    assert result["statuses"][0]["state"] == "HOLD"
    assert len(result["transitions"]) == 1
    assert save.call_args.args[1][0]["to_state"] == "HOLD"


def test_notification_cooldown_suppresses_repeat_but_not_severity_escalation():
    recent = [
        {
            "symbol": "TEST",
            "to_state": "EXIT_WARNING",
            "changed_at": "2026-08-16T14:25:00+00:00",
            "actionable": True,
        }
    ]
    repeated = {
        "symbol": "TEST",
        "from_state": "HOLD",
        "to_state": "EXIT_WARNING",
        "changed_at": "2026-08-16T14:30:00+00:00",
        "actionable": True,
    }
    escalated = {**repeated, "to_state": "EXIT"}

    assert _select_notifications([repeated], recent, cooldown_seconds=900) == []
    assert _select_notifications([escalated], recent, cooldown_seconds=900) == [escalated]
