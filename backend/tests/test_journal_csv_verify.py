"""Journal ↔ CSV verification and event ledger tests."""
from __future__ import annotations

from integrations.robinhood.csv_importer import parse_robinhood_csv
from integrations.robinhood.journal_verifier import (
    is_manual_journal_ledger_row,
    verify_journal_trades_against_ledger,
)
from integrations.robinhood.portfolio_rebuilder import rebuild_portfolio

EXAMPLE_CSV = """Activity Date,Process Date,Settle Date,Instrument,Description,Trans Code,Quantity,Price,Amount
2025-05-01,2025-05-01,2025-05-02,,Robinhood instant bank transfer,RTP,,,$900.00
2025-05-02,2025-05-02,2025-05-03,,Stock lending payment,SLIP,,,$0.01
2025-05-03,2025-05-03,2025-05-04,AMC,AMC Entertainment,Buy,20,1.95,($39.00)
"""


def test_event_rows_separate_from_holdings():
    rows, _ = parse_robinhood_csv(EXAMPLE_CSV)
    rebuild = rebuild_portfolio(rows)
    assert len(rebuild.event_ledger) == 2
    assert {e.trans_code for e in rebuild.event_ledger} == {"RTP", "SLIP"}
    assert {h.symbol for h in rebuild.open_holdings} == {"AMC"}


def test_manual_journal_row_detection():
    assert is_manual_journal_ledger_row(trans_code="MANUAL", description="test")
    assert is_manual_journal_ledger_row(trans_code="BUY", description="note [journal #12]")
    assert not is_manual_journal_ledger_row(trans_code="BUY", description="Robinhood buy")


def test_verify_journal_matched_csv():
    rows, _ = parse_robinhood_csv(EXAMPLE_CSV)

    def _hash(trade_id: int, leg: str) -> str:
        return f"fake-{trade_id}-{leg}"

    checks = verify_journal_trades_against_ledger(
        1,
        csv_rows=rows,
        journal_ledger_hash_fn=_hash,
        ledger_has_hash_fn=lambda _h: False,
        list_journal_trades_fn=lambda limit=500: [
            {"id": 7, "symbol": "AMC", "quantity": 20, "entry_price": 1.95},
        ],
        load_ledger_rows_fn=lambda _a: [],
    )
    assert checks[0]["status"] == "matched_csv"


def test_verify_journal_missing():
    rows, _ = parse_robinhood_csv(EXAMPLE_CSV)
    checks = verify_journal_trades_against_ledger(
        1,
        csv_rows=rows,
        journal_ledger_hash_fn=lambda tid, leg: f"h-{tid}-{leg}",
        ledger_has_hash_fn=lambda _h: False,
        list_journal_trades_fn=lambda limit=500: [
            {"id": 3, "symbol": "NVDA", "quantity": 5, "entry_price": 100},
        ],
        load_ledger_rows_fn=lambda _a: [],
    )
    assert checks[0]["status"] == "missing"
