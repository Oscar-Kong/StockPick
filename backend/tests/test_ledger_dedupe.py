"""Tests for duplicate Robinhood ledger row handling."""
from __future__ import annotations

import pytest

from integrations.robinhood.ledger_dedupe import dedupe_parsed_rows, is_incomplete_ghost_row
from integrations.robinhood.models import ParsedCsvRow
from integrations.robinhood.portfolio_rebuilder import rebuild_portfolio


def _row(**kwargs) -> ParsedCsvRow:
    defaults = {
        "activity_date": "",
        "process_date": "",
        "instrument": "AMC",
        "description": "",
        "trans_code": "BUY",
        "quantity": 20.0,
        "price": 1.95,
        "amount": 0.0,
        "row_type": "buy",
        "row_hash": "x",
    }
    defaults.update(kwargs)
    return ParsedCsvRow(**defaults)  # type: ignore[arg-type]


def test_ghost_row_detection():
    assert is_incomplete_ghost_row(_row(activity_date="", amount=0.0))
    assert not is_incomplete_ghost_row(_row(activity_date="2025-05-03", amount=-39.0))


def test_dedupe_same_trade_with_and_without_date():
    dated = _row(activity_date="2025-05-03", amount=-39.0, row_hash="a")
    ghost = _row(activity_date="", amount=0.0, row_hash="b")
    deduped, removed = dedupe_parsed_rows([dated, ghost])
    assert removed >= 1
    assert len(deduped) == 1
    assert deduped[0].activity_date == "2025-05-03"


def test_dedupe_lidr_lots_from_ghost_reimport():
    dated = [
        _row(instrument="LIDR", quantity=10.123456, price=1.2, amount=-12.15, activity_date="2025-05-05", row_hash="l1"),
        _row(instrument="LIDR", quantity=13.443238, price=1.18, amount=-15.86, activity_date="2025-05-05", row_hash="l2"),
    ]
    ghosts = [
        _row(instrument="LIDR", quantity=14.0, price=2.12, amount=0.0, activity_date="", row_hash="g1"),
        _row(instrument="LIDR", quantity=9.0, price=2.13, amount=0.0, activity_date="", row_hash="g2"),
    ]
    deduped, _ = dedupe_parsed_rows(dated + ghosts)
    rebuild = rebuild_portfolio(deduped)
    lidr = next(h for h in rebuild.open_holdings if h.symbol == "LIDR")
    assert lidr.shares == pytest.approx(23.566694, rel=1e-4)
