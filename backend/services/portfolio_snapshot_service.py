"""Portfolio snapshots, CSV import orchestration, holdings reconstruction."""
from __future__ import annotations

import logging

from data.portfolio_store import (
    DEFAULT_ACCOUNT_ID,
    get_account_cash,
    get_current_holdings,
    get_latest_portfolio_snapshot,
    get_or_create_account,
    list_uploads,
    load_all_ledger_rows,
    mark_sync,
    record_upload,
    save_holdings,
    save_portfolio_snapshot,
    set_account_cash,
    update_account_source,
    upsert_ledger_rows,
)
from integrations.robinhood.csv_importer import parse_robinhood_csv
from integrations.robinhood.portfolio_rebuilder import rebuild_portfolio, validation_report
from integrations.robinhood.snaptrade_client import SnapTradeClient
from models.schemas import Bucket, PortfolioHolding
from utils.pydantic_util import model_to_dict

logger = logging.getLogger(__name__)

DISCLAIMER = (
    "Daily decisions are model-generated research outputs, not financial advice. "
    "Review before trading. The app does not place trades."
)


def _rebuild_from_store(account_id: int = DEFAULT_ACCOUNT_ID):
    rows = load_all_ledger_rows(account_id)
    return rebuild_portfolio(rows)


def import_robinhood_csv(content: str | bytes, filename: str, *, cash: float | None = None) -> dict:
    rows, warnings = parse_robinhood_csv(content)
    account = get_or_create_account()
    account_id = account["id"]

    file_id = record_upload(account_id, filename, len(rows), 0, warnings)
    imported, skipped = upsert_ledger_rows(account_id, rows, source_file_id=file_id)

    rebuild = _rebuild_from_store(account_id)
    saved = save_holdings(account_id, rebuild.open_holdings, source="csv")

    closed = [
        {
            "symbol": c.symbol,
            "total_bought": c.total_bought,
            "total_sold": c.total_sold,
            "realized_pl": c.realized_pl,
            "last_activity": c.last_activity,
        }
        for c in rebuild.closed_positions
    ]

    if cash is not None:
        final_cash = float(cash)
    else:
        final_cash = max(0.0, rebuild.cash_delta)

    set_account_cash(account_id, final_cash)
    acct = update_account_source("csv", cash=final_cash)

    total_est = sum(h["shares"] * h["avg_cost"] for h in saved) + final_cash
    save_portfolio_snapshot(
        account_id,
        final_cash,
        total_est,
        saved,
        "csv",
        closed_positions=closed,
    )
    mark_sync(
        account_id,
        "csv",
        trades_imported=imported,
        trades_skipped=skipped,
        message=f"Imported {imported} ledger rows from {filename}",
    )

    return {
        "filename": filename,
        "trades_parsed": len(rows),
        "trades_imported": imported,
        "trades_skipped": skipped,
        "holdings_count": len(saved),
        "holdings": saved,
        "closed_positions": closed,
        "cash": final_cash,
        "cash_delta_from_csv": rebuild.cash_delta,
        "warnings": warnings + rebuild.warnings,
        "account": acct,
    }


def validate_robinhood_csv(content: str | bytes) -> dict:
    """Dev validation: parse + rebuild without persisting."""
    rows, warnings = parse_robinhood_csv(content)
    rebuild = rebuild_portfolio(rows)
    per_symbol = validation_report(rows, rebuild)
    return {
        "parsed_row_count": len(rows),
        "excluded_rows": rebuild.excluded_rows,
        "unknown_trans_codes": rebuild.unknown_trans_codes,
        "cash_impact": rebuild.cash_delta,
        "open_holdings": [
            {
                "symbol": h.symbol,
                "shares": h.shares,
                "avg_cost": h.avg_cost,
                "bucket": h.bucket,
                "total_bought": h.total_bought,
                "total_sold": h.total_sold,
                "realized_pl": h.realized_pl,
            }
            for h in rebuild.open_holdings
        ],
        "closed_positions": [
            {
                "symbol": c.symbol,
                "total_bought": c.total_bought,
                "total_sold": c.total_sold,
                "realized_pl": c.realized_pl,
                "last_activity": c.last_activity,
            }
            for c in rebuild.closed_positions
        ],
        "per_symbol_validation": per_symbol,
        "warnings": warnings + rebuild.warnings,
    }


def import_robinhood_csv_and_decide(content: str | bytes, filename: str, *, cash: float | None = None) -> dict:
    result = import_robinhood_csv(content, filename, cash=cash)
    if result.get("holdings_count", 0) > 0:
        try:
            from services.portfolio_decision_service import run_stored_portfolio_decision

            decision = run_stored_portfolio_decision(trigger="manual", persist=True)
            result["decision"] = model_to_dict(decision)
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
    rebuild = _rebuild_from_store()
    saved = save_holdings(DEFAULT_ACCOUNT_ID, rebuild.open_holdings, source=account["source"])
    cash = get_account_cash()
    closed = [
        {
            "symbol": c.symbol,
            "total_bought": c.total_bought,
            "total_sold": c.total_sold,
            "realized_pl": c.realized_pl,
            "last_activity": c.last_activity,
        }
        for c in rebuild.closed_positions
    ]
    total_est = sum(h["shares"] * h["avg_cost"] for h in saved) + cash
    snap = save_portfolio_snapshot(DEFAULT_ACCOUNT_ID, cash, total_est, saved, account["source"], closed_positions=closed)
    return {"holdings": saved, "cash": cash, "closed_positions": closed, "snapshot": snap}


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
    snap = get_latest_portfolio_snapshot()
    closed = (snap or {}).get("closed_positions") or []
    return {
        "account": account,
        "cash": account["cash_balance"],
        "holdings": holdings,
        "closed_positions": closed,
        "data_source": account["source"],
        "disclaimer": DISCLAIMER,
        "is_demo_data": account["source"] == "demo",
    }


def list_import_history() -> list[dict]:
    return list_uploads()
