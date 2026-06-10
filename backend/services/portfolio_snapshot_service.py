"""Portfolio snapshots, CSV import orchestration, holdings reconstruction."""
from __future__ import annotations

import logging

from data.portfolio_store import (
    DEFAULT_ACCOUNT_ID,
    get_account_cash,
    get_current_holdings,
    get_or_create_account,
    list_uploads,
    load_all_trades,
    mark_sync,
    record_upload,
    save_holdings,
    save_portfolio_snapshot,
    update_account_source,
    upsert_trades,
)
from integrations.robinhood.base import reconstruct_holdings
from integrations.robinhood.csv_importer import parse_robinhood_csv
from integrations.robinhood.snaptrade_client import SnapTradeClient
from models.schemas import Bucket, PortfolioHolding

logger = logging.getLogger(__name__)

DISCLAIMER = (
    "Daily decisions are model-generated research outputs, not financial advice. Review before trading."
)


def import_robinhood_csv(content: str | bytes, filename: str, *, cash: float | None = None) -> dict:
    trades, warnings = parse_robinhood_csv(content)
    account = get_or_create_account()
    account_id = account["id"]

    file_id = record_upload(account_id, filename, len(trades), 0, warnings)
    imported, skipped = upsert_trades(account_id, trades, source_file_id=file_id)

    all_trades = load_all_trades(account_id)
    holdings = reconstruct_holdings(all_trades)
    saved = save_holdings(account_id, holdings, source="csv")

    acct = update_account_source("csv", cash=cash)
    total_est = sum(h["shares"] * h["avg_cost"] for h in saved)
    save_portfolio_snapshot(
        account_id,
        acct["cash_balance"],
        total_est + acct["cash_balance"],
        saved,
        "csv",
    )
    mark_sync(
        account_id,
        "csv",
        trades_imported=imported,
        trades_skipped=skipped,
        message=f"Imported {imported} trades from {filename}",
    )

    return {
        "filename": filename,
        "trades_parsed": len(trades),
        "trades_imported": imported,
        "trades_skipped": skipped,
        "holdings_count": len(saved),
        "holdings": saved,
        "warnings": warnings,
        "account": acct,
    }


def import_robinhood_csv_and_decide(content: str | bytes, filename: str, *, cash: float | None = None) -> dict:
    result = import_robinhood_csv(content, filename, cash=cash)
    if result.get("holdings_count", 0) > 0:
        try:
            from services.portfolio_decision_service import run_stored_portfolio_decision

            decision = run_stored_portfolio_decision(trigger="manual", persist=True)
            result["decision"] = decision.model_dump()
        except Exception as exc:
            result["warnings"] = list(result.get("warnings") or []) + [f"Decision after import skipped: {exc}"]
    return result


def sync_brokerage_if_configured() -> dict:
    client = SnapTradeClient()
    if not client.is_configured():
        return {"synced": False, "source": get_or_create_account().get("source", "manual"), "message": "No brokerage API configured"}
    result = client.sync_holdings()
    return {"synced": False, "source": "snaptrade", "message": result.message}


def refresh_holdings_snapshot() -> dict:
    account = get_or_create_account()
    holdings = get_current_holdings()
    cash = get_account_cash()
    total_est = sum(h["shares"] * h["avg_cost"] for h in holdings)
    snap = save_portfolio_snapshot(
        DEFAULT_ACCOUNT_ID,
        cash,
        total_est + cash,
        holdings,
        account["source"],
    )
    return {"holdings": holdings, "cash": cash, "snapshot": snap}


def holdings_to_request() -> tuple[float, list[PortfolioHolding]]:
    cash = get_account_cash()
    rows = get_current_holdings()
    holdings = [
        PortfolioHolding(
            symbol=r["symbol"],
            shares=r["shares"],
            avg_cost=r["avg_cost"],
            bucket=Bucket(r["bucket"]) if r["bucket"] in ("penny", "compounder", "medium") else Bucket.penny,
        )
        for r in rows
    ]
    return cash, holdings


def get_current_portfolio() -> dict:
    account = get_or_create_account()
    holdings = get_current_holdings()
    return {
        "account": account,
        "cash": account["cash_balance"],
        "holdings": holdings,
        "data_source": account["source"],
        "disclaimer": DISCLAIMER,
    }


def list_import_history() -> list[dict]:
    return list_uploads()
