"""Tests for Robinhood MCP realized P/L parsing."""
from __future__ import annotations

from integrations.robinhood.mcp_pnl import parse_pnl_trade_history_pages, summarize_realized_trades


def test_summarize_realized_trades_splits_equity_and_events():
    trades = [
        {"symbol": "ZVIA", "realized_gain": "11.55"},
        {"symbol": "", "realized_gain": "-9.1"},
        {"symbol": "", "realized_gain": "26.66"},
        {"symbol": "CYH", "realized_gain": "9.2"},
    ]
    summary = summarize_realized_trades(trades)
    assert summary.equity == 20.75
    assert summary.events == 17.56
    assert summary.total == 38.31
    assert summary.trade_count == 4


def test_parse_pnl_trade_history_pages():
    payload = {
        "data": {
            "trades": [
                {"symbol": "AMC", "realized_gain": "-1.46"},
                {"symbol": "", "realized_gain": "24.82"},
            ],
            "next_cursor": "",
        }
    }
    summary = parse_pnl_trade_history_pages([payload])
    assert summary.total == 23.36
    assert summary.equity == -1.46
    assert summary.events == 24.82
