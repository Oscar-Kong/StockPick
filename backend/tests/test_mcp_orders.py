"""Tests for Robinhood MCP order → ledger parsing."""
from __future__ import annotations

from integrations.robinhood.mcp_orders import parse_mcp_equity_orders


def test_parse_mcp_equity_orders_executions():
    payload = {
        "data": {
            "orders": [
                {
                    "id": "order-1",
                    "symbol": "AMC",
                    "side": "buy",
                    "type": "market",
                    "state": "filled",
                    "average_price": "2.010000",
                    "placed_agent": "user",
                    "created_at": "2026-07-01T17:16:59.786202Z",
                    "executions": [
                        {
                            "id": "exec-1",
                            "price": "2.010000",
                            "quantity": "60.000000",
                            "timestamp": "2026-07-01T17:16:59.913Z",
                        }
                    ],
                },
                {
                    "id": "order-2",
                    "symbol": "CYH",
                    "side": "sell",
                    "type": "market",
                    "state": "filled",
                    "average_price": "3.740000",
                    "placed_agent": "user",
                    "created_at": "2026-07-02T13:49:08.556876Z",
                    "executions": [
                        {
                            "id": "exec-2",
                            "price": "3.740000",
                            "quantity": "20.000000",
                            "timestamp": "2026-07-02T13:49:08.7Z",
                        }
                    ],
                },
            ]
        }
    }
    rows = parse_mcp_equity_orders(payload)
    assert len(rows) == 2
    by_sym = {r.instrument: r for r in rows}
    assert by_sym["AMC"].row_type == "buy"
    assert by_sym["AMC"].quantity == 60.0
    assert by_sym["AMC"].price == 2.01
    assert by_sym["AMC"].amount < 0
    assert by_sym["CYH"].row_type == "sell"
    assert by_sym["CYH"].amount > 0
    assert by_sym["AMC"].row_hash != by_sym["CYH"].row_hash


def test_parse_mcp_equity_orders_skips_unfilled():
    payload = {"data": {"orders": [{"symbol": "XYZ", "side": "buy", "state": "cancelled"}]}}
    assert parse_mcp_equity_orders(payload) == []
