"""Cash-only MCP sync must not run daily decision (avoids false UI timeouts)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from services.portfolio_snapshot_service import import_robinhood_mcp_and_decide


def test_cash_only_mcp_sync_skips_decision(isolated_backend_env):
    snapshot = MagicMock()
    snapshot.holdings = []
    snapshot.order_rows = []
    snapshot.buying_power = 2105.82
    snapshot.portfolio_value = 2105.82
    snapshot.account_id = "acct-1"

    with patch("services.portfolio_snapshot_service.RobinhoodMcpClient") as client_cls:
        client = client_cls.return_value
        client.is_configured.return_value = True
        client.fetch_live_portfolio = MagicMock(return_value=snapshot)

        # asyncio.run(client.fetch_live_portfolio(...)) — make fetch awaitable
        async def _fetch(**_kwargs):
            return snapshot

        client.fetch_live_portfolio = _fetch

        with patch(
            "services.portfolio_snapshot_service.get_or_create_account",
            return_value={"id": 1},
        ), patch(
            "services.portfolio_snapshot_service.replace_trade_ledger",
            return_value=(0, 0, 0),
        ), patch(
            "services.portfolio_snapshot_service.purge_duplicate_trades",
        ), patch(
            "services.portfolio_snapshot_service.repair_phantom_journal_buys",
        ), patch(
            "services.portfolio_snapshot_service._rebuild_from_store",
            return_value=MagicMock(closed_positions=[], event_ledger=[]),
        ), patch(
            "services.portfolio_snapshot_service._apply_ledger_to_portfolio",
            return_value={
                "holdings_count": 0,
                "holdings": [],
                "cash": 2105.82,
            },
        ), patch(
            "services.portfolio_snapshot_service.update_account_source",
            return_value={"id": 1, "source": "robinhood_mcp"},
        ), patch(
            "services.portfolio_snapshot_service.mark_sync",
        ), patch(
            "data.freshness_store.mark_freshness_updated",
        ), patch(
            "data.freshness_store.clear_freshness_flag",
        ), patch(
            "services.refresh_orchestrator.refresh_prices_for_holdings",
            return_value={"updated": 0},
        ), patch(
            "services.portfolio_decision_service.run_stored_portfolio_decision",
        ) as run_decision, patch(
            "data.portfolio_store.save_decision_snapshot",
        ) as save_snap:
            result = import_robinhood_mcp_and_decide(run_decision=True)

    assert result["holdings_count"] == 0
    assert result.get("decision_skipped") == "cash_only"
    assert result.get("decision_cleared") is True
    run_decision.assert_not_called()
    save_snap.assert_called_once()
    payload = save_snap.call_args.args[2]
    assert payload["items"] == []
    assert payload["invested_value"] == 0.0
