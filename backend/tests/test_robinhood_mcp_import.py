"""Tests for Robinhood MCP import — live positions vs ledger."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from integrations.robinhood.models import PortfolioRebuildResult, ReconstructedHolding
from services.portfolio_snapshot_service import (
    ensure_holdings_reconciled,
    get_current_portfolio,
    import_robinhood_mcp_and_decide,
)


def test_mcp_import_uses_live_positions_not_ledger_rebuild():
    live = [
        ReconstructedHolding(symbol="AMC", shares=66.0, avg_cost=2.01, bucket="penny"),
        ReconstructedHolding(symbol="SPCX", shares=5.0, avg_cost=135.0, bucket="compounder"),
    ]
    ledger_rebuild = PortfolioRebuildResult(
        open_holdings=[
            ReconstructedHolding(symbol="ALXO", shares=22.99, avg_cost=2.18, bucket="penny"),
            ReconstructedHolding(symbol="AMC", shares=126.0, avg_cost=2.01, bucket="penny"),
        ],
        closed_positions=[],
        cash_delta=0,
        event_ledger=[],
        excluded_rows=[],
        unknown_trans_codes=[],
        warnings=[],
    )
    snapshot = MagicMock()
    snapshot.holdings = live
    snapshot.buying_power = 229.64
    snapshot.portfolio_value = 1000.0
    snapshot.account_id = "555676394"
    snapshot.order_rows = [MagicMock(row_hash="abc")]

    applied_rebuild: PortfolioRebuildResult | None = None

    def capture_apply(_account_id, rebuild, *, source, cash_override=None):
        nonlocal applied_rebuild
        applied_rebuild = rebuild
        return {
            "holdings": [{"symbol": h.symbol, "shares": h.shares, "avg_cost": h.avg_cost} for h in rebuild.open_holdings],
            "cash": cash_override,
            "holdings_count": len(rebuild.open_holdings),
            "closed_positions": [],
            "misc_events": [],
        }

    with patch("services.portfolio_snapshot_service.RobinhoodMcpClient") as client_cls:
        client_cls.return_value.is_configured.return_value = True
        with patch("services.portfolio_snapshot_service.asyncio.run", return_value=snapshot):
            with patch("services.portfolio_snapshot_service.get_or_create_account", return_value={"id": 1, "source": "manual"}):
                with patch(
                    "services.portfolio_snapshot_service.replace_trade_ledger",
                    return_value=(1, 0, 42),
                ) as replace_ledger:
                    with patch("services.portfolio_snapshot_service.purge_duplicate_trades"):
                        with patch("services.portfolio_snapshot_service.repair_phantom_journal_buys"):
                            with patch("services.portfolio_snapshot_service._rebuild_from_store", return_value=ledger_rebuild):
                                with patch("services.portfolio_snapshot_service._apply_ledger_to_portfolio", side_effect=capture_apply):
                                    with patch("services.portfolio_snapshot_service.update_account_source", return_value={}):
                                        with patch("services.portfolio_snapshot_service.mark_sync", return_value={}):
                                            with patch("data.freshness_store.mark_freshness_updated"):
                                                with patch("data.freshness_store.clear_freshness_flag"):
                                                    with patch(
                                                        "services.refresh_orchestrator.refresh_prices_for_holdings",
                                                        return_value={"refreshed": 2},
                                                    ) as refresh_prices:
                                                        result = import_robinhood_mcp_and_decide(run_decision=False)

    assert applied_rebuild is not None
    symbols = [h.symbol for h in applied_rebuild.open_holdings]
    assert symbols == ["AMC", "SPCX"]
    assert result["holdings_count"] == 2
    assert result["robinhood_account_number"] == "555676394"
    replace_ledger.assert_called_once_with(1, snapshot.order_rows)
    refresh_prices.assert_called_once_with(force=True)


def test_mcp_import_with_decision_refreshes_prices_then_decides():
    live = [ReconstructedHolding(symbol="AMC", shares=66.0, avg_cost=2.01, bucket="penny")]
    snapshot = MagicMock()
    snapshot.holdings = live
    snapshot.buying_power = 100.0
    snapshot.portfolio_value = 200.0
    snapshot.account_id = "1"
    snapshot.order_rows = []

    decision = MagicMock()
    decision.model_dump = MagicMock(return_value={"items": []})

    with patch("services.portfolio_snapshot_service.RobinhoodMcpClient") as client_cls:
        client_cls.return_value.is_configured.return_value = True
        with patch("services.portfolio_snapshot_service.asyncio.run", return_value=snapshot):
            with patch("services.portfolio_snapshot_service.get_or_create_account", return_value={"id": 1}):
                with patch(
                    "services.portfolio_snapshot_service.replace_trade_ledger",
                    return_value=(0, 0, 0),
                ):
                    with patch("services.portfolio_snapshot_service.purge_duplicate_trades"):
                        with patch("services.portfolio_snapshot_service.repair_phantom_journal_buys"):
                            with patch(
                                "services.portfolio_snapshot_service._rebuild_from_store",
                                return_value=MagicMock(closed_positions=[], event_ledger=[]),
                            ):
                                with patch("services.portfolio_snapshot_service._apply_ledger_to_portfolio") as apply:
                                    apply.return_value = {
                                        "holdings": [{"symbol": "AMC", "shares": 66.0}],
                                        "cash": 100.0,
                                        "holdings_count": 1,
                                        "closed_positions": [],
                                        "misc_events": [],
                                    }
                                    with patch("services.portfolio_snapshot_service.update_account_source", return_value={}):
                                        with patch("services.portfolio_snapshot_service.mark_sync", return_value={}):
                                            with patch("data.freshness_store.mark_freshness_updated"):
                                                with patch("data.freshness_store.clear_freshness_flag"):
                                                    with patch(
                                                        "services.refresh_orchestrator.refresh_prices_for_holdings",
                                                        return_value={"refreshed": 1},
                                                    ) as refresh_prices:
                                                        with patch(
                                                            "services.portfolio_decision_service.run_stored_portfolio_decision",
                                                            return_value=decision,
                                                        ) as run_decision:
                                                            with patch(
                                                                "services.portfolio_snapshot_service.model_to_dict",
                                                                return_value={"items": []},
                                                            ):
                                                                result = import_robinhood_mcp_and_decide(run_decision=True)

    refresh_prices.assert_called_once_with(force=True)
    run_decision.assert_called_once()
    assert "decision" in result


def test_robinhood_mcp_skips_ledger_reconcile():
    with patch("services.portfolio_snapshot_service.get_or_create_account", return_value={"source": "robinhood_mcp"}):
        with patch("services.portfolio_snapshot_service.repair_ledger_fill_prices") as repair:
            with patch("services.portfolio_snapshot_service.refresh_holdings_snapshot") as refresh:
                assert ensure_holdings_reconciled() is False
    repair.assert_not_called()
    refresh.assert_not_called()


def test_get_current_portfolio_preserves_mcp_holdings():
    holdings = [{"symbol": "AMC", "shares": 66.0, "avg_cost": 2.01, "bucket": "penny"}]
    with patch("services.portfolio_snapshot_service.ensure_holdings_reconciled", return_value=False):
        with patch(
            "services.portfolio_snapshot_service.get_or_create_account",
            return_value={"source": "robinhood_mcp", "cash_balance": 100},
        ):
            with patch("services.portfolio_snapshot_service.get_current_holdings", return_value=holdings):
                with patch("services.portfolio_snapshot_service.get_latest_portfolio_snapshot", return_value={}):
                    with patch("services.portfolio_snapshot_service.resolve_portfolio_cash", return_value=(100.0, "buying_power")):
                        with patch("services.portfolio_snapshot_service.get_reserved_cash", return_value=0.0):
                            out = get_current_portfolio()
    assert out["holdings"] == holdings
