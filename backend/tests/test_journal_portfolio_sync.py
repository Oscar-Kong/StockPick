"""Journal trade → Home portfolio sync tests."""
from __future__ import annotations

from unittest.mock import patch

from services.portfolio_snapshot_service import (
    _journal_ledger_hash,
    evaluate_portfolio_sync_result,
    is_journal_trade_synced,
    journal_trade_sync_status,
)


def test_evaluate_sync_result_imported():
    ok, msg = evaluate_portfolio_sync_result({"imported": 1, "skipped": 0, "holdings_count": 2})
    assert ok is True
    assert msg


def test_evaluate_sync_result_already_synced():
    ok, msg = evaluate_portfolio_sync_result(
        {"imported": 0, "skipped": 1, "message": "Portfolio refreshed (trade already synced)"}
    )
    assert ok is True


def test_evaluate_sync_result_no_changes():
    ok, msg = evaluate_portfolio_sync_result({"imported": 0, "skipped": 0, "holdings_count": 0})
    assert ok is False
    assert msg


def test_evaluate_sync_result_ledger_ok_decision_warns():
    ok, msg = evaluate_portfolio_sync_result(
        {
            "imported": 1,
            "skipped": 0,
            "message": "Portfolio updated",
            "decision_error": "price timeout",
        }
    )
    assert ok is True
    assert "decision refresh" in (msg or "")


def test_evaluate_sync_result_decision_fail_no_ledger():
    ok, msg = evaluate_portfolio_sync_result({"imported": 0, "skipped": 0, "decision_error": "no holdings"})
    assert ok is False
    assert msg == "no holdings"


def test_journal_trade_sync_status_needs_quantity():
    status, synced = journal_trade_sync_status(trade_id=1, quantity=None)
    assert status == "needs_quantity"
    assert synced is False


def test_journal_trade_sync_status_pending():
    with patch("services.portfolio_snapshot_service.is_journal_trade_synced", return_value=False):
        status, synced = journal_trade_sync_status(trade_id=5, quantity=10)
    assert status == "pending"
    assert synced is False


def test_journal_trade_sync_status_synced():
    with patch("services.portfolio_snapshot_service.is_journal_trade_synced", return_value=True):
        status, synced = journal_trade_sync_status(trade_id=5, quantity=10)
    assert status == "synced"
    assert synced is True


def test_is_journal_trade_synced_checks_buy_leg_hash():
    buy_hash = _journal_ledger_hash(42, "buy")
    with patch("data.portfolio_store.ledger_has_row_hash", return_value=True) as has_hash:
        assert is_journal_trade_synced(42) is True
    has_hash.assert_called_once_with(buy_hash)
