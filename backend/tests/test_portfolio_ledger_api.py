"""Portfolio ledger API tests."""
from __future__ import annotations

from datetime import datetime

import pytest

from data.portfolio_store import SessionLocal, TradeHistory, init_portfolio_db, list_ledger_rows_detailed
from services.portfolio_ledger_service import (
    create_ledger_entry,
    list_ledger_api,
    preview_robinhood_csv,
    remove_ledger_entry,
    update_ledger_entry,
)


def _clear_test_rows() -> None:
    session = SessionLocal()
    try:
        session.query(TradeHistory).filter(TradeHistory.symbol == "ZZTEST").delete()
        session.commit()
    finally:
        session.close()


def test_ledger_crud_and_rebuild():
    init_portfolio_db()
    _clear_test_rows()

    created = create_ledger_entry(
        {
            "symbol": "ZZTEST",
            "side": "buy",
            "quantity": 10,
            "price": 5.0,
            "amount": -50.0,
            "activity_date": "2026-06-01",
            "process_date": "2026-06-01",
            "trans_code": "MANUAL",
        }
    )
    assert created["symbol"] == "ZZTEST"

    updated = update_ledger_entry(
        created["id"],
        {
            "side": "sell",
            "quantity": 10,
            "price": 6.0,
            "amount": 60.0,
            "activity_date": "2026-06-02",
        },
    )
    assert updated["side"] == "sell"

    api = list_ledger_api()
    zz = [r for r in api["rows"] if r["symbol"] == "ZZTEST"]
    assert len(zz) == 1
    assert api["open_holdings"] == []

    remove_ledger_entry(created["id"])
    assert [r for r in list_ledger_rows_detailed() if r["symbol"] == "ZZTEST"] == []


def test_ledger_save_locks_row():
    init_portfolio_db()
    _clear_test_rows()

    created = create_ledger_entry(
        {
            "symbol": "ZZTEST",
            "side": "buy",
            "quantity": 10,
            "price": 5.0,
            "amount": -50.0,
            "activity_date": "2026-06-01",
            "process_date": "2026-06-01",
            "trans_code": "MANUAL",
        }
    )
    assert created.get("locked") is False

    saved = update_ledger_entry(created["id"], {"lock": True})
    assert saved.get("locked") is True

    with pytest.raises(ValueError, match="locked"):
        update_ledger_entry(created["id"], {"quantity": 5})

    with pytest.raises(ValueError, match="locked"):
        remove_ledger_entry(created["id"])

    # cleanup via direct DB delete for test isolation
    session = SessionLocal()
    try:
        session.query(TradeHistory).filter(TradeHistory.symbol == "ZZTEST").delete()
        session.commit()
    finally:
        session.close()


def test_csv_preview_returns_rows():
    init_portfolio_db()
    csv = """Activity Date,Process Date,Settle Date,Instrument,Description,Trans Code,Quantity,Price,Amount
2026-06-01,2026-06-01,2026-06-02,ABC,Test,Buy,5,10.00,($50.00)
"""
    preview = preview_robinhood_csv(csv.encode(), "test.csv")
    assert preview["filename"] == "test.csv"
    assert len(preview["rows"]) == 1
    assert preview["rows"][0]["symbol"] == "ABC"
