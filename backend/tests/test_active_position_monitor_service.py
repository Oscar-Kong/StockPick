from __future__ import annotations

from unittest.mock import patch

from services.active_position_monitor_service import (
    _select_notifications,
    get_active_position_monitor_status,
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
        patch("services.active_position_monitor_service.save_active_quote_refresh_status") as save_status,
    ):
        result = refresh_and_store_active_quotes()

    assert result["quote_only"] is True
    save.assert_called_once()
    assert save.call_args.args[0] == {"TEST": 10.25}
    assert save.call_args.kwargs["as_of"]
    assert save.call_args.kwargs["active_symbols"] == ["TEST"]
    assert save_status.call_args.args[0]["as_of"]


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


def test_read_path_marks_persisted_fresh_state_stale_when_quote_ages_out():
    with (
        patch(
            "services.active_position_monitor_service.get_active_position_states",
            return_value=[
                {
                    "symbol": "TEST",
                    "state": "HOLD",
                    "actionable": True,
                    "data_status": "fresh",
                    "quote_as_of": "2020-01-01T14:30:00Z",
                    "updated_at": "2020-01-01T14:30:30Z",
                }
            ],
        ),
        patch(
            "services.active_position_monitor_service.get_active_quote_snapshot",
            return_value={"as_of": "2020-01-01T14:30:00Z", "quotes": {}},
        ),
        patch(
            "services.active_position_monitor_service.get_active_quote_refresh_status",
            return_value={"daily_budget_used": 42},
        ),
        patch(
            "services.active_position_monitor_service.list_active_position_transitions",
            return_value=[],
        ),
    ):
        result = get_active_position_monitor_status()

    assert result["statuses"][0]["state"] == "DATA_STALE"
    assert result["statuses"][0]["actionable"] is False
    assert result["quote_as_of"] == "2020-01-01T14:30:00Z"
    assert result["provider_usage"]["daily_budget_used"] == 42


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


def test_notification_cooldown_looks_past_non_actionable_transition():
    recent = [
        {
            "symbol": "TEST",
            "to_state": "HOLD",
            "changed_at": "2026-08-16T14:29:00+00:00",
            "actionable": False,
        },
        {
            "symbol": "TEST",
            "to_state": "TRIM",
            "changed_at": "2026-08-16T14:25:00+00:00",
            "actionable": True,
        },
    ]
    repeated = {
        "symbol": "TEST",
        "from_state": "HOLD",
        "to_state": "TRIM",
        "changed_at": "2026-08-16T14:30:00+00:00",
        "actionable": True,
    }

    assert _select_notifications([repeated], recent, cooldown_seconds=900) == []
