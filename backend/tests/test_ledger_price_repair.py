"""Robinhood ledger fill-price repair and holdings reconciliation."""
from __future__ import annotations

import pytest

from data.portfolio_store import (
    DEFAULT_ACCOUNT_ID,
    SessionLocal,
    TradeHistory,
    get_current_holdings,
    init_portfolio_db,
    load_all_ledger_rows,
    repair_ledger_fill_prices,
    update_account_source,
    upsert_ledger_rows,
)
from integrations.robinhood.csv_importer import parse_robinhood_csv
from integrations.robinhood.models import ParsedCsvRow
from integrations.robinhood.portfolio_rebuilder import rebuild_portfolio
from services.portfolio_snapshot_service import ensure_holdings_reconciled, refresh_holdings_snapshot


def _clear_lidr_rows() -> None:
    session = SessionLocal()
    try:
        session.query(TradeHistory).filter(TradeHistory.symbol == "LIDR").delete()
        session.commit()
    finally:
        session.close()


def test_repair_lidr_price_from_amount_overrides_wrong_price_column():
    init_portfolio_db()
    _clear_lidr_rows()
    session = SessionLocal()
    try:
        session.add(
            TradeHistory(
                account_id=DEFAULT_ACCOUNT_ID,
                symbol="LIDR",
                side="buy",
                quantity=10.0,
                price=1.19,
                amount=-19.10,
                trans_code="BUY",
                description="Lidar Technologies",
                activity_date="2025-06-01",
                process_date="2025-06-01",
                row_hash="test-lidr-191",
                created_at=__import__("datetime").datetime.utcnow(),
            )
        )
        session.commit()
    finally:
        session.close()

    assert repair_ledger_fill_prices() == 1
    rebuild = rebuild_portfolio(load_all_ledger_rows())
    lidr = next(h for h in rebuild.open_holdings if h.symbol == "LIDR")
    assert lidr.avg_cost == pytest.approx(1.91, rel=1e-4)
    assert lidr.shares == pytest.approx(10.0)


def test_reimport_upgrades_existing_semantic_row_price():
    init_portfolio_db()
    _clear_lidr_rows()
    csv = """Activity Date,Process Date,Settle Date,Instrument,Description,Trans Code,Quantity,Price,Amount
2025-06-01,2025-06-01,2025-06-02,LIDR,Lidar Technologies,Buy,10,1.19,($19.10)
"""
    rows, _ = parse_robinhood_csv(csv)
    assert rows[0].price == pytest.approx(1.91)

    session = SessionLocal()
    try:
        session.add(
            TradeHistory(
                account_id=DEFAULT_ACCOUNT_ID,
                symbol="LIDR",
                side="buy",
                quantity=10.0,
                price=1.19,
                amount=-19.10,
                trans_code="BUY",
                description="Lidar Technologies",
                activity_date="2025-06-01",
                process_date="2025-06-01",
                row_hash="legacy-lidr-hash",
                created_at=__import__("datetime").datetime.utcnow(),
            )
        )
        session.commit()
    finally:
        session.close()

    imported, skipped = upsert_ledger_rows(DEFAULT_ACCOUNT_ID, rows)
    assert imported == 0
    assert skipped == 1

    session = SessionLocal()
    try:
        row = session.query(TradeHistory).filter(TradeHistory.symbol == "LIDR").one()
        assert row.price == pytest.approx(1.91, rel=1e-4)
    finally:
        session.close()


def test_refresh_holdings_persists_repaired_avg_cost():
    init_portfolio_db()
    _clear_lidr_rows()
    session = SessionLocal()
    try:
        session.add(
            TradeHistory(
                account_id=DEFAULT_ACCOUNT_ID,
                symbol="LIDR",
                side="buy",
                quantity=10.0,
                price=1.19,
                amount=-19.10,
                trans_code="BUY",
                description="Lidar Technologies",
                activity_date="2025-06-01",
                process_date="2025-06-01",
                row_hash="test-lidr-refresh",
                created_at=__import__("datetime").datetime.utcnow(),
            )
        )
        session.commit()
    finally:
        session.close()

    refresh_holdings_snapshot()
    saved = [h for h in get_current_holdings() if h["symbol"] == "LIDR"]
    assert len(saved) == 1
    assert saved[0]["avg_cost"] == pytest.approx(1.91, rel=1e-4)


def test_ensure_holdings_reconciled_fixes_stale_saved_avg_cost():
    init_portfolio_db()
    _clear_lidr_rows()
    row = ParsedCsvRow(
        activity_date="2025-06-01",
        process_date="2025-06-01",
        instrument="LIDR",
        description="Lidar Technologies",
        trans_code="BUY",
        quantity=10.0,
        price=1.91,
        amount=-19.10,
        row_type="buy",
        row_hash="ensure-lidr",
    )
    upsert_ledger_rows(DEFAULT_ACCOUNT_ID, [row])

    session = SessionLocal()
    try:
        from data.portfolio_store import PortfolioHoldingRow

        session.query(PortfolioHoldingRow).filter(PortfolioHoldingRow.symbol == "LIDR").delete()
        session.add(
            PortfolioHoldingRow(
                account_id=DEFAULT_ACCOUNT_ID,
                symbol="LIDR",
                shares=10.0,
                avg_cost=1.19,
                bucket="penny",
                updated_at=__import__("datetime").datetime.utcnow(),
            )
        )
        session.commit()
    finally:
        session.close()

    update_account_source("csv")
    assert ensure_holdings_reconciled() is True
    saved = [h for h in get_current_holdings() if h["symbol"] == "LIDR"]
    assert saved[0]["avg_cost"] == pytest.approx(1.91, rel=1e-4)
