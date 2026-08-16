from __future__ import annotations

from data.portfolio_store import (
    get_active_position_states,
    init_portfolio_db,
    list_active_position_transitions,
    save_active_position_monitor_result,
)


def test_active_position_store_upserts_status_and_appends_only_supplied_transitions():
    init_portfolio_db()
    status = {
        "symbol": "TEST",
        "state": "HOLD",
        "actionable": False,
        "price": 10.2,
        "evidence": ["No boundary crossed"],
    }
    transition = {
        "symbol": "TEST",
        "from_state": None,
        "to_state": "HOLD",
        "actionable": False,
        "evidence": ["No boundary crossed"],
    }

    save_active_position_monitor_result([status], [transition], as_of="2026-08-16T14:30:00Z")
    save_active_position_monitor_result(
        [{**status, "price": 10.3}], [], as_of="2026-08-16T14:35:00Z"
    )

    states = get_active_position_states()
    transitions = list_active_position_transitions(limit=10)
    assert states[0]["price"] == 10.3
    assert states[0]["updated_at"] == "2026-08-16T14:35:00Z"
    assert len(transitions) == 1
    assert transitions[0]["to_state"] == "HOLD"


def test_active_position_store_removes_states_for_closed_holdings():
    save_active_position_monitor_result(
        [{"symbol": "CLOSED", "state": "HOLD"}],
        [],
        as_of="2026-08-16T14:40:00Z",
    )

    save_active_position_monitor_result([], [], as_of="2026-08-16T14:45:00Z")

    assert get_active_position_states() == []
