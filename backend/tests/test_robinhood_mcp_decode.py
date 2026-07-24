"""Fixture tests for Robinhood MCP decode, positions, and completeness."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from integrations.robinhood.mcp_client import (
    LivePortfolioSnapshot,
    SnapshotCompleteness,
    assess_positions_parse,
    parse_equity_positions,
)
from integrations.robinhood.mcp_decode import (
    RobinhoodToolError,
    decode_tool_result,
    positions_payload_is_genuinely_empty,
)
from integrations.robinhood.mcp_orders import _order_cursor
from integrations.robinhood.models import ReconstructedHolding
from services.portfolio_snapshot_service import import_robinhood_mcp_and_decide


def _tool_result(*, is_error=False, content=None, structured=None):
    return SimpleNamespace(
        isError=is_error,
        content=content or [],
        structuredContent=structured,
    )


def test_decode_raises_on_is_error_rate_limit():
    result = _tool_result(
        is_error=True,
        content=[SimpleNamespace(text='{"error":"RATE_LIMIT_EXCEEDED"}')],
    )
    with pytest.raises(RobinhoodToolError) as exc_info:
        decode_tool_result(result, tool="get_equity_positions")
    assert exc_info.value.retryable is True
    assert "RATE_LIMIT" in exc_info.value.message


def test_decode_prefers_structured_content_over_text():
    result = _tool_result(
        content=[SimpleNamespace(text="Portfolio loaded successfully")],
        structured={"positions": [{"symbol": "AAPL", "quantity": "2"}]},
    )
    decoded = decode_tool_result(result, tool="get_equity_positions")
    assert decoded["positions"][0]["symbol"] == "AAPL"
    holdings = parse_equity_positions(decoded)
    assert len(holdings) == 1
    assert holdings[0].symbol == "AAPL"
    assert holdings[0].shares == 2.0


def test_decode_merges_multi_content_blocks_for_cursor():
    result = _tool_result(
        content=[
            SimpleNamespace(text='{"orders":[{"id":"1","symbol":"AAPL","side":"buy","state":"filled","quantity":1,"average_price":10}]}'),
            SimpleNamespace(text='{"cursor":"abc"}'),
        ]
    )
    decoded = decode_tool_result(result, tool="get_equity_orders")
    assert isinstance(decoded, dict)
    assert _order_cursor(decoded) == "abc"


def test_decode_binary_content_block():
    result = _tool_result(content=[SimpleNamespace(data=b'{"buying_power": 12.5}')])
    decoded = decode_tool_result(result, tool="get_portfolio")
    assert decoded["buying_power"] == 12.5


def test_symbol_keyed_holdings_parse():
    payload = {
        "holdings": {
            "AAPL": {"quantity": "2", "average_buy_price": "190"},
            "MSFT": {"quantity": 1, "average_buy_price": 400},
        }
    }
    holdings = parse_equity_positions(payload)
    by_sym = {h.symbol: h for h in holdings}
    assert by_sym["AAPL"].shares == 2.0
    assert by_sym["AAPL"].avg_cost == 190.0
    assert by_sym["MSFT"].shares == 1.0


def test_nested_data_positions_still_work():
    payload = {"data": {"positions": [{"symbol": "AMC", "quantity": 10, "average_buy_price": 2}]}}
    holdings = parse_equity_positions(payload)
    assert holdings[0].symbol == "AMC"


def test_empty_positions_is_genuine_cash_only():
    assert positions_payload_is_genuinely_empty({"positions": []}) is True
    holdings, warnings = assess_positions_parse({"positions": []})
    assert holdings == []
    assert warnings == []


def test_unparseable_nonempty_payload_warns_not_cash_only():
    payload = {"positions": [{"ticker_name": "AAPL", "units": 2}]}
    holdings, warnings = assess_positions_parse(payload)
    assert holdings == []
    assert warnings
    assert positions_payload_is_genuinely_empty(payload) is False


def test_mcp_import_skips_ledger_clear_when_history_incomplete():
    from integrations.robinhood.mcp_client import SnapshotCompleteness, LivePortfolioSnapshot

    snapshot = LivePortfolioSnapshot(
        holdings=[ReconstructedHolding(symbol="AMC", shares=10, avg_cost=2.0, bucket="penny")],
        buying_power=100.0,
        portfolio_value=120.0,
        account_id="1",
        raw_positions={"positions": []},
        raw_portfolio={"buying_power": 100},
        order_rows=[],
        completeness=SnapshotCompleteness(
            positions_ok=True,
            portfolio_ok=True,
            orders_ok=False,
            orders_truncated=False,
            history_complete=False,
            warnings=["Order history incomplete: timeout"],
        ),
    )

    with patch("services.portfolio_snapshot_service.RobinhoodMcpClient") as client_cls:
        client_cls.return_value.is_configured.return_value = True
        with patch("services.portfolio_snapshot_service.asyncio.run", return_value=snapshot):
            with patch("services.portfolio_snapshot_service.get_or_create_account", return_value={"id": 1}):
                with patch("services.portfolio_snapshot_service.replace_trade_ledger") as replace:
                    with patch("services.portfolio_snapshot_service.clear_trade_ledger") as clear:
                        with patch(
                            "services.portfolio_snapshot_service._rebuild_from_store",
                            return_value=MagicMock(
                                closed_positions=[],
                                event_ledger=[],
                            ),
                        ):
                            with patch(
                                "services.portfolio_snapshot_service._apply_ledger_to_portfolio",
                                return_value={
                                    "holdings": [{"symbol": "AMC"}],
                                    "cash": 100.0,
                                    "holdings_count": 1,
                                    "closed_positions": [],
                                    "misc_events": [],
                                },
                            ):
                                with patch("services.portfolio_snapshot_service.update_account_source", return_value={}):
                                    with patch("services.portfolio_snapshot_service.mark_sync"):
                                        with patch("data.freshness_store.mark_freshness_updated"):
                                            with patch("data.freshness_store.clear_freshness_flag"):
                                                with patch(
                                                    "services.refresh_orchestrator.refresh_prices_for_holdings",
                                                    return_value={},
                                                ):
                                                    result = import_robinhood_mcp_and_decide(run_decision=False)

    replace.assert_not_called()
    clear.assert_not_called()
    assert result["sync_status"] == "degraded"
    assert result["ledger_replaced"] is False
    assert result["history_complete"] is False


def test_mcp_import_replaces_ledger_when_history_complete():
    from integrations.robinhood.mcp_client import SnapshotCompleteness, LivePortfolioSnapshot

    snapshot = LivePortfolioSnapshot(
        holdings=[ReconstructedHolding(symbol="AMC", shares=10, avg_cost=2.0, bucket="penny")],
        buying_power=100.0,
        portfolio_value=120.0,
        account_id="1",
        raw_positions={"positions": []},
        raw_portfolio={"buying_power": 100},
        order_rows=[MagicMock(row_hash="abc")],
        completeness=SnapshotCompleteness(
            positions_ok=True,
            portfolio_ok=True,
            orders_ok=True,
            orders_truncated=False,
            history_complete=True,
            warnings=[],
        ),
    )

    with patch("services.portfolio_snapshot_service.RobinhoodMcpClient") as client_cls:
        client_cls.return_value.is_configured.return_value = True
        with patch("services.portfolio_snapshot_service.asyncio.run", return_value=snapshot):
            with patch("services.portfolio_snapshot_service.get_or_create_account", return_value={"id": 1}):
                with patch(
                    "services.portfolio_snapshot_service.replace_trade_ledger",
                    return_value=(1, 0, 5),
                ) as replace:
                    with patch("services.portfolio_snapshot_service.purge_duplicate_trades"):
                        with patch("services.portfolio_snapshot_service.repair_phantom_journal_buys"):
                            with patch(
                                "services.portfolio_snapshot_service._rebuild_from_store",
                                return_value=MagicMock(closed_positions=[], event_ledger=[]),
                            ):
                                with patch(
                                    "services.portfolio_snapshot_service._apply_ledger_to_portfolio",
                                    return_value={
                                        "holdings": [{"symbol": "AMC"}],
                                        "cash": 100.0,
                                        "holdings_count": 1,
                                        "closed_positions": [],
                                        "misc_events": [],
                                    },
                                ):
                                    with patch("services.portfolio_snapshot_service.update_account_source", return_value={}):
                                        with patch("services.portfolio_snapshot_service.mark_sync"):
                                            with patch("data.freshness_store.mark_freshness_updated"):
                                                with patch("data.freshness_store.clear_freshness_flag"):
                                                    with patch(
                                                        "services.refresh_orchestrator.refresh_prices_for_holdings",
                                                        return_value={},
                                                    ):
                                                        result = import_robinhood_mcp_and_decide(run_decision=False)

    replace.assert_called_once()
    assert result["ledger_replaced"] is True
    assert result["sync_status"] == "ok"
