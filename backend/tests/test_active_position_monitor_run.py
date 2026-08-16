from __future__ import annotations

from datetime import datetime, timedelta, timezone

from services.active_position_monitor import ActivePositionMonitor


def test_monitor_emits_transition_only_when_state_changes():
    monitor = ActivePositionMonitor()
    now = datetime(2026, 8, 16, 14, 30, tzinfo=timezone.utc)
    holdings = [{"symbol": "TEST", "shares": 10, "avg_cost": 10.0, "bucket": "penny"}]
    quotes = {"TEST": {"price": 10.2, "as_of": now.isoformat()}}

    first = monitor.evaluate(holdings=holdings, quotes=quotes, previous_states={}, now=now)
    second = monitor.evaluate(
        holdings=holdings,
        quotes=quotes,
        previous_states={"TEST": first.statuses[0].state},
        now=now,
    )

    assert first.statuses[0].state == "HOLD"
    assert first.statuses[0].unrealized_pl_pct == 2.0
    assert len(first.transitions) == 1
    assert first.transitions[0].from_state is None
    assert second.transitions == []


def test_monitor_marks_missing_quote_as_stale_without_action():
    monitor = ActivePositionMonitor()
    now = datetime(2026, 8, 16, 14, 30, tzinfo=timezone.utc)

    result = monitor.evaluate(
        holdings=[{"symbol": "MISS", "shares": 5, "avg_cost": 4.0, "bucket": "penny"}],
        quotes={},
        previous_states={"MISS": "HOLD"},
        now=now,
    )

    status = result.statuses[0]
    assert status.state == "DATA_STALE"
    assert status.actionable is False
    assert status.data_status == "missing_quote"


def test_stop_breach_requires_two_spaced_monitor_samples_and_exit_is_sticky():
    monitor = ActivePositionMonitor()
    now = datetime(2026, 8, 16, 14, 30, tzinfo=timezone.utc)
    holdings = [{"symbol": "TEST", "shares": 10, "avg_cost": 10.0, "bucket": "penny"}]
    quotes = {"TEST": {"price": 9.4, "as_of": now.isoformat()}}

    first = monitor.evaluate(holdings=holdings, quotes=quotes, previous_states={}, now=now)
    second = monitor.evaluate(
        holdings=holdings,
        quotes={"TEST": {"price": 9.4, "as_of": (now + timedelta(minutes=5)).isoformat()}},
        previous_states={"TEST": first.statuses[0].state},
        previous_state_times={"TEST": now.isoformat()},
        now=now + timedelta(minutes=5),
    )
    third = monitor.evaluate(
        holdings=holdings,
        quotes={"TEST": {"price": 9.4, "as_of": (now + timedelta(minutes=10)).isoformat()}},
        previous_states={"TEST": second.statuses[0].state},
        previous_state_times={"TEST": (now + timedelta(minutes=5)).isoformat()},
        now=now + timedelta(minutes=10),
    )

    assert first.statuses[0].state == "EXIT_WARNING"
    assert first.statuses[0].actionable is False
    assert second.statuses[0].state == "EXIT"
    assert second.statuses[0].actionable is True
    assert third.statuses[0].state == "EXIT"
    assert third.transitions == []


def test_compounder_does_not_inherit_penny_stop_and_target_policy():
    now = datetime(2026, 8, 16, 14, 30, tzinfo=timezone.utc)
    result = ActivePositionMonitor().evaluate(
        holdings=[{"symbol": "LONG", "shares": 2, "avg_cost": 100.0, "bucket": "compounder"}],
        quotes={"LONG": {"price": 94.0, "as_of": now.isoformat()}},
        previous_states={},
        now=now,
    )

    assert result.statuses[0].state == "HOLD"
    assert result.statuses[0].stop_price is None
    assert result.statuses[0].target_price is None
