from __future__ import annotations

from services.active_position_monitor import PositionSnapshot, evaluate_intraday_position


def test_stale_position_data_suppresses_actionable_decision():
    result = evaluate_intraday_position(
        PositionSnapshot(symbol="TEST", price=10.0, quote_age_seconds=181, stop_price=9.0)
    )
    assert result.state == "DATA_STALE"
    assert result.actionable is False


def test_confirmed_stop_breach_exits_and_near_stop_warns():
    warning = evaluate_intraday_position(
        PositionSnapshot(symbol="TEST", price=9.15, quote_age_seconds=10, stop_price=9.0)
    )
    breached = evaluate_intraday_position(
        PositionSnapshot(
            symbol="TEST",
            price=8.95,
            quote_age_seconds=10,
            stop_price=9.0,
            confirmation_bars=2,
        )
    )
    assert warning.state == "EXIT_WARNING"
    assert breached.state == "EXIT"


def test_target_reached_trims_without_refetching_research_context():
    result = evaluate_intraday_position(
        PositionSnapshot(
            symbol="TEST",
            price=12.1,
            quote_age_seconds=5,
            stop_price=9.0,
            target_price=12.0,
        )
    )
    assert result.state == "TRIM"
    assert "target" in result.evidence[0].lower()
