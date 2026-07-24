"""Tests for Robinhood MCP portfolio parsing (no live API)."""
from __future__ import annotations

from integrations.robinhood.mcp_client import (
    _pick_account_id,
    parse_buying_power,
    parse_equity_positions,
    parse_portfolio_value,
)


def test_parse_equity_positions_nested():
    payload = {
        "equity_positions": [
            {
                "symbol": "amc",
                "quantity": 60,
                "average_buy_price": 2.01,
            },
            {
                "instrument": {"symbol": "SPCX"},
                "shares": 5,
                "cost_basis": 675,
            },
        ]
    }
    holdings = parse_equity_positions(payload)
    by_sym = {h.symbol: h for h in holdings}
    assert by_sym["AMC"].shares == 60
    assert by_sym["AMC"].avg_cost == 2.01
    assert by_sym["SPCX"].shares == 5
    assert by_sym["SPCX"].avg_cost == 135.0


def test_parse_buying_power_and_value():
    payload = {"portfolio": {"buying_power": 1250.5, "equity": 9876.0}}
    assert parse_buying_power(payload) == 1250.5
    assert parse_portfolio_value(payload) == 9876.0


def test_parse_equity_positions_skips_zero_qty():
    payload = {"positions": [{"symbol": "XYZ", "quantity": 0}]}
    assert parse_equity_positions(payload) == []


def test_pick_account_id_prefers_default_nested():
    payload = {
        "data": {
            "accounts": [
                {"account_number": "111", "is_default": True},
                {"account_number": "222", "is_default": False, "agentic_allowed": True},
            ]
        }
    }
    assert _pick_account_id(payload, None) == "111"


def test_pick_account_id_respects_env_preferred():
    payload = {"data": {"accounts": [{"account_number": "111"}, {"account_number": "222"}]}}
    assert _pick_account_id(payload, "222") == "222"


def test_parse_equity_positions_symbol_keyed_map():
    payload = {"holdings": {"AAPL": {"quantity": 2, "average_buy_price": 190}}}
    holdings = parse_equity_positions(payload)
    assert len(holdings) == 1
    assert holdings[0].symbol == "AAPL"
