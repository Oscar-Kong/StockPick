"""Slim MCP sync updates positions without wiping the Activity ledger."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
from unittest.mock import MagicMock, patch

from integrations.robinhood.mcp_client import RobinhoodMcpClient, SnapshotCompleteness
from integrations.robinhood.mcp_orders import pick_newest_order_row
from integrations.robinhood.models import ParsedCsvRow, ReconstructedHolding
from services.portfolio_snapshot_service import import_robinhood_mcp_and_decide


def test_pick_newest_order_row():
    older = ParsedCsvRow(
        activity_date="01/01/2026",
        process_date="01/01/2026",
        instrument="AAA",
        description="old",
        trans_code="MCP-BUY",
        quantity=1,
        price=1,
        amount=-1,
        row_type="buy",
        row_hash="a",
        executed_at=datetime(2026, 1, 1),
    )
    newer = ParsedCsvRow(
        activity_date="06/01/2026",
        process_date="06/01/2026",
        instrument="BBB",
        description="new",
        trans_code="MCP-SELL",
        quantity=2,
        price=3,
        amount=6,
        row_type="sell",
        row_hash="b",
        executed_at=datetime(2026, 6, 1),
    )
    picked = pick_newest_order_row([older, newer])
    assert len(picked) == 1
    assert picked[0].instrument == "BBB"


def test_slim_import_updates_positions_without_ledger_replace(isolated_backend_env):
    completeness = SnapshotCompleteness(
        positions_ok=True,
        portfolio_ok=True,
        orders_ok=True,
        orders_truncated=True,
        history_complete=False,
        warnings=["Slim sync: latest trade only"],
    )
    snapshot = MagicMock()
    snapshot.holdings = [
        ReconstructedHolding(symbol="AMC", shares=10, avg_cost=2.0, bucket="penny"),
    ]
    snapshot.order_rows = [
        ParsedCsvRow(
            activity_date="07/01/2026",
            process_date="07/01/2026",
            instrument="AMC",
            description="latest",
            trans_code="MCP-BUY",
            quantity=1,
            price=2.5,
            amount=-2.5,
            row_type="buy",
            row_hash="x",
            executed_at=datetime(2026, 7, 1),
        )
    ]
    snapshot.buying_power = 500.0
    snapshot.portfolio_value = 520.0
    snapshot.account_id = "222"
    snapshot.completeness = completeness
    snapshot.realized_pnl = None

    with patch("services.portfolio_snapshot_service.RobinhoodMcpClient") as client_cls:
        client = client_cls.return_value
        client.is_configured.return_value = True

        async def _fetch(**kwargs):
            assert kwargs.get("orders_mode") == "latest"
            return snapshot

        client.fetch_live_portfolio = _fetch

        with patch(
            "services.portfolio_snapshot_service.get_or_create_account",
            return_value={"id": 1},
        ), patch(
            "services.portfolio_snapshot_service.replace_trade_ledger",
        ) as replace_ledger, patch(
            "services.portfolio_snapshot_service._rebuild_from_store",
            return_value=MagicMock(closed_positions=[], event_ledger=[]),
        ), patch(
            "services.portfolio_snapshot_service._apply_ledger_to_portfolio",
            return_value={
                "holdings_count": 1,
                "holdings": [{"symbol": "AMC", "shares": 10, "avg_cost": 2.0}],
                "cash": 500.0,
            },
        ), patch(
            "services.portfolio_snapshot_service.update_account_source",
            return_value={"id": 1, "source": "robinhood_mcp"},
        ), patch(
            "services.portfolio_snapshot_service.mark_sync",
        ), patch(
            "services.refresh_orchestrator.refresh_prices_for_holdings",
            return_value={"refreshed": 1},
        ), patch(
            "services.refresh_orchestrator.portfolio_refresh",
        ):
            result = import_robinhood_mcp_and_decide(run_decision=False, orders_mode="latest")

    replace_ledger.assert_not_called()
    assert result["holdings_count"] == 1
    assert result["cash"] == 500.0
    assert result["ledger_replaced"] is False
    assert result["orders_mode"] == "latest"
    assert result["latest_trade"]["symbol"] == "AMC"


def test_slim_fetch_keeps_required_portfolio_when_optional_orders_timeout():
    client = RobinhoodMcpClient(token_storage=MagicMock())

    @asynccontextmanager
    async def fake_session():
        yield object()

    async def fake_call(_session, name, _arguments):
        if name == "get_accounts":
            return {"accounts": [{"account_number": "acct", "is_default": True}]}
        if name == "get_equity_positions":
            return {"positions": [{"symbol": "AAPL", "quantity": 2, "average_buy_price": 100}]}
        if name == "get_portfolio":
            return {"portfolio": {"buying_power": 50, "equity": 250}}
        raise AssertionError(name)

    async def slow_orders(*_args, **_kwargs):
        await asyncio.sleep(1)

    client._session = fake_session  # type: ignore[method-assign]
    with (
        patch.object(client, "_call_tool", side_effect=fake_call),
        patch.object(client, "_fetch_filled_orders", side_effect=slow_orders),
        patch("integrations.robinhood.mcp_client.sync_timeout_sec", return_value=0.15),
    ):
        snapshot = asyncio.run(
            client.fetch_live_portfolio(orders_mode="latest", include_realized_pnl=False)
        )

    assert [holding.symbol for holding in snapshot.holdings] == ["AAPL"]
    assert snapshot.buying_power == 50
    assert snapshot.completeness.positions_ok is True
    assert snapshot.completeness.portfolio_ok is True
    assert snapshot.completeness.orders_ok is False
    assert any("timed out" in warning.lower() for warning in snapshot.completeness.warnings)
