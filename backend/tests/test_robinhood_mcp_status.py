"""Robinhood MCP status + connectivity probe diagnostics."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from services.portfolio_snapshot_service import robinhood_mcp_status


def test_status_without_probe_includes_login_script_and_auth_flags():
    with patch("services.portfolio_snapshot_service.RobinhoodMcpClient") as client_cls:
        client_cls.return_value.is_configured.return_value = True
        with patch(
            "services.portfolio_snapshot_service._token_expiry_meta",
            return_value={"token_expires_at": 1784823317.0, "token_expired": False},
        ):
            status = robinhood_mcp_status(probe=False)

    assert status["enabled"] is True
    assert status["authenticated"] is True
    assert status["login_script"] == "./scripts/robinhood-mcp-login.sh"
    assert status["sync_script"] == "./scripts/sync-robinhood-mcp.sh"
    assert status["token_expired"] is False
    assert status.get("probe") is None


def test_status_probe_ok_cash_only_reports_healthy_empty_positions():
    with patch("services.portfolio_snapshot_service.RobinhoodMcpClient") as client_cls:
        client = client_cls.return_value
        client.is_configured.return_value = True
        client.probe_connection = MagicMock(
            return_value={
                "ok": True,
                "latency_ms": 1200,
                "account_id": "555676394",
                "accounts_count": 2,
                "holdings_count": 0,
                "cash": 2105.82,
                "equity_value": 0.0,
                "portfolio_value": 2105.82,
                "error": None,
                "needs_reauth": False,
                "message": "Connected — account is cash-only (0 equity positions)",
            }
        )
        with patch(
            "services.portfolio_snapshot_service._token_expiry_meta",
            return_value={"token_expires_at": None, "token_expired": False},
        ):
            status = robinhood_mcp_status(probe=True)

    assert status["authenticated"] is True
    probe = status["probe"]
    assert probe["ok"] is True
    assert probe["holdings_count"] == 0
    assert probe["cash"] == 2105.82
    assert probe["needs_reauth"] is False


def test_status_probe_auth_failure_flags_reauth():
    with patch("services.portfolio_snapshot_service.RobinhoodMcpClient") as client_cls:
        client = client_cls.return_value
        client.is_configured.return_value = True
        client.probe_connection = MagicMock(
            return_value={
                "ok": False,
                "latency_ms": 80,
                "account_id": None,
                "accounts_count": 0,
                "holdings_count": 0,
                "cash": None,
                "equity_value": None,
                "portfolio_value": None,
                "error": "Robinhood MCP session expired. Re-authenticate with: ./scripts/robinhood-mcp-login.sh",
                "needs_reauth": True,
                "message": "Session expired — re-run ./scripts/robinhood-mcp-login.sh",
            }
        )
        with patch(
            "services.portfolio_snapshot_service._token_expiry_meta",
            return_value={"token_expires_at": 1.0, "token_expired": True},
        ):
            status = robinhood_mcp_status(probe=True)

    assert status["token_expired"] is True
    assert status["probe"]["ok"] is False
    assert status["probe"]["needs_reauth"] is True


def test_status_unauthenticated_skips_live_probe():
    with patch("services.portfolio_snapshot_service.RobinhoodMcpClient") as client_cls:
        client = client_cls.return_value
        client.is_configured.return_value = False
        client.probe_connection = MagicMock()
        with patch(
            "services.portfolio_snapshot_service._token_expiry_meta",
            return_value={"token_expires_at": None, "token_expired": False},
        ):
            status = robinhood_mcp_status(probe=True)

    client.probe_connection.assert_not_called()
    assert status["authenticated"] is False
    assert status["probe"]["ok"] is False
    assert status["probe"]["needs_reauth"] is True
    assert "./scripts/robinhood-mcp-login.sh" in status["probe"]["message"]
