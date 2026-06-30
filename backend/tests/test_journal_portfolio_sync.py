"""Journal → portfolio ledger sync (exit-only closes, phantom buy repair)."""
from __future__ import annotations

from datetime import datetime

import pytest

from data.portfolio_store import (
    DEFAULT_ACCOUNT_ID,
    SessionLocal,
    TradeHistory,
    get_current_holdings,
    init_portfolio_db,
    repair_phantom_journal_buys,
    upsert_ledger_rows,
)
from integrations.robinhood.models import ParsedCsvRow
from integrations.robinhood.portfolio_rebuilder import rebuild_portfolio
from services.portfolio_snapshot_service import apply_manual_trade_to_portfolio, refresh_holdings_snapshot


def _clear_symbol(symbol: str) -> None:
    session = SessionLocal()
    try:
        session.query(TradeHistory).filter(TradeHistory.symbol == symbol).delete()
        session.commit()
    finally:
        session.close()


def test_exit_only_journal_sync_closes_csv_position():
    """Closed journal with entry_price=0 should sell CSV shares, not add phantom buys."""
    init_portfolio_db()
    _clear_symbol("HIVE")

    csv_rows = [
        ParsedCsvRow(
            activity_date="2026-06-10",
            process_date="2026-06-10",
            instrument="HIVE",
            description="HIVE buy 1",
            trans_code="BUY",
            quantity=10.0,
            price=3.74,
            amount=-37.4,
            row_type="buy",
            row_hash="hive-csv-1",
        ),
        ParsedCsvRow(
            activity_date="2026-06-15",
            process_date="2026-06-15",
            instrument="HIVE",
            description="HIVE buy 2",
            trans_code="BUY",
            quantity=10.0,
            price=3.94,
            amount=-39.45,
            row_type="buy",
            row_hash="hive-csv-2",
        ),
    ]
    upsert_ledger_rows(DEFAULT_ACCOUNT_ID, csv_rows)

    result = apply_manual_trade_to_portfolio(
        trade_id=99,
        symbol="HIVE",
        side="long",
        entry_time=datetime(2026, 6, 24),
        entry_price=0.0,
        quantity=20.0,
        exit_price=4.62,
        notes="Closed HIVE",
    )
    assert result is not None
    assert result["holdings_count"] == 0

    session = SessionLocal()
    try:
        manual_buys = (
            session.query(TradeHistory)
            .filter(
                TradeHistory.symbol == "HIVE",
                TradeHistory.trans_code == "MANUAL",
                TradeHistory.side == "buy",
            )
            .count()
        )
        assert manual_buys == 0
    finally:
        session.close()


def test_repair_phantom_journal_buys():
    init_portfolio_db()
    _clear_symbol("TEST")

    session = SessionLocal()
    try:
        session.add(
            TradeHistory(
                account_id=DEFAULT_ACCOUNT_ID,
                symbol="TEST",
                side="buy",
                quantity=20.0,
                price=0.0,
                amount=0.0,
                trans_code="MANUAL",
                description="Manual trade entry [journal #42]",
                activity_date="2026-06-24",
                process_date="2026-06-24",
                row_hash="phantom-buy-42",
                created_at=datetime.utcnow(),
            )
        )
        session.add(
            TradeHistory(
                account_id=DEFAULT_ACCOUNT_ID,
                symbol="TEST",
                side="sell",
                quantity=20.0,
                price=4.62,
                amount=92.4,
                trans_code="MANUAL",
                description="Manual trade entry [journal #42]",
                activity_date="2026-06-24",
                process_date="2026-06-24",
                row_hash="phantom-sell-42",
                created_at=datetime.utcnow(),
            )
        )
        session.commit()
    finally:
        session.close()

    removed = repair_phantom_journal_buys(DEFAULT_ACCOUNT_ID)
    assert removed == 1

    session = SessionLocal()
    try:
        buys = session.query(TradeHistory).filter(TradeHistory.symbol == "TEST", TradeHistory.side == "buy").count()
        sells = session.query(TradeHistory).filter(TradeHistory.symbol == "TEST", TradeHistory.side == "sell").count()
        assert buys == 0
        assert sells == 1
    finally:
        session.close()
