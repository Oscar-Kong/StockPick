"""Tests for Robinhood CSV import and trade hashing."""
from __future__ import annotations

from integrations.robinhood.base import reconstruct_holdings
from integrations.robinhood.csv_importer import parse_robinhood_csv, trade_row_hash
from integrations.robinhood.models import ParsedTrade
from datetime import datetime


SAMPLE_CSV = """Activity Date,Process Date,Settle Date,Instrument,Description,Trans Code,Quantity,Price,Amount
2024-01-15,2024-01-15,2024-01-16,AAPL,Apple Inc.,Buy,10,150.00,1500.00
2024-02-01,2024-02-01,2024-02-02,AAPL,Apple Inc.,Sell,2,160.00,320.00
2024-03-10,2024-03-10,2024-03-11,SOFI,Sofi Technologies,Buy,100,7.50,750.00
"""


def test_parse_robinhood_csv():
    trades, warnings = parse_robinhood_csv(SAMPLE_CSV)
    assert len(trades) >= 3
    assert all(t.row_hash for t in trades)
    symbols = {t.symbol for t in trades}
    assert "AAPL" in symbols
    assert "SOFI" in symbols


def test_trade_row_hash_stable():
    h1 = trade_row_hash(
        symbol="AAPL",
        side="buy",
        quantity=10,
        price=150,
        executed_at=datetime(2024, 1, 15),
        order_id=None,
    )
    h2 = trade_row_hash(
        symbol="AAPL",
        side="buy",
        quantity=10,
        price=150,
        executed_at=datetime(2024, 1, 15),
        order_id=None,
    )
    assert h1 == h2


def test_reconstruct_holdings():
    trades = [
        ParsedTrade("AAPL", "buy", 10, 150, row_hash="a"),
        ParsedTrade("AAPL", "sell", 2, 160, row_hash="b"),
        ParsedTrade("SOFI", "buy", 100, 7.5, row_hash="c"),
    ]
    holdings = reconstruct_holdings(trades)
    by_sym = {h.symbol: h for h in holdings}
    assert by_sym["AAPL"].shares == 8
    assert by_sym["SOFI"].shares == 100
