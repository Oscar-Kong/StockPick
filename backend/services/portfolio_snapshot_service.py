"""Portfolio snapshots, CSV import orchestration, holdings reconstruction."""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime

from data.portfolio_store import (
    DEFAULT_ACCOUNT_ID,
    get_account_cash,
    get_account_reserved_cash,
    get_current_holdings,
    get_latest_portfolio_snapshot,
    get_or_create_account,
    list_uploads,
    load_all_ledger_rows,
    mark_sync,
    clear_trade_ledger,
    clear_csv_sourced_ledger,
    purge_duplicate_trades,
    record_upload,
    repair_ledger_fill_prices,
    repair_phantom_journal_buys,
    save_holdings,
    save_portfolio_snapshot,
    set_account_cash,
    set_account_ipo_order,
    set_account_reserved_cash,
    update_account_source,
    upsert_ledger_rows,
)
from integrations.robinhood.csv_importer import parse_robinhood_csv
from integrations.robinhood.journal_verifier import verify_journal_trades_against_ledger
from integrations.robinhood.models import MiscEventRow, PortfolioRebuildResult
from integrations.robinhood.portfolio_rebuilder import rebuild_portfolio, validation_report
from integrations.robinhood.mcp_client import RobinhoodMcpClient
from integrations.robinhood.snaptrade_client import SnapTradeClient
from core.sleeve import normalize_bucket
from models.schemas import Bucket, PortfolioHolding
from utils.pydantic_util import model_to_dict

logger = logging.getLogger(__name__)


def _rebuild_from_store(account_id: int = DEFAULT_ACCOUNT_ID) -> PortfolioRebuildResult:
    rows = load_all_ledger_rows(account_id)
    return rebuild_portfolio(rows)


def _misc_events_payload(events: list[MiscEventRow]) -> list[dict]:
    return [
        {
            "activity_date": e.activity_date,
            "trans_code": e.trans_code,
            "description": e.description,
            "amount": e.amount,
            "instrument": e.instrument,
        }
        for e in events
    ]


def _apply_ledger_to_portfolio(
    account_id: int,
    rebuild: PortfolioRebuildResult,
    *,
    source: str,
    cash_override: float | None = None,
) -> dict:
    """Persist holdings + event ledger + closed positions from a rebuild."""
    saved = save_holdings(account_id, rebuild.open_holdings, source=source)
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
    misc_events = _misc_events_payload(rebuild.event_ledger)

    if cash_override is not None:
        final_cash = float(cash_override)
    else:
        final_cash = max(0.0, rebuild.cash_delta)

    set_account_cash(account_id, final_cash)
    total_est = sum(h["shares"] * h["avg_cost"] for h in saved) + final_cash
    save_portfolio_snapshot(
        account_id,
        final_cash,
        total_est,
        saved,
        source,
        closed_positions=closed,
        extra={"misc_events": misc_events},
    )
    return {
        "holdings": saved,
        "closed_positions": closed,
        "misc_events": misc_events,
        "cash": final_cash,
        "holdings_count": len(saved),
    }


def _verify_journal_after_import(account_id: int, csv_rows) -> list[dict]:
    from data.cache import list_trades
    from data.portfolio_store import ledger_has_row_hash

    return verify_journal_trades_against_ledger(
        account_id,
        csv_rows=csv_rows,
        journal_ledger_hash_fn=_journal_ledger_hash,
        ledger_has_hash_fn=ledger_has_row_hash,
        list_journal_trades_fn=list_trades,
        load_ledger_rows_fn=load_all_ledger_rows,
    )


def _holdings_drift_from_ledger(account_id: int = DEFAULT_ACCOUNT_ID) -> bool:
    """True when saved holdings disagree with ledger reconstruction."""
    account = get_or_create_account()
    if account.get("source") not in ("csv", "snaptrade", "robinhood_mcp"):
        return False
    rows = load_all_ledger_rows(account_id)
    if not rows:
        return False
    rebuilt = {h.symbol: h for h in rebuild_portfolio(rows).open_holdings}
    saved = {h["symbol"]: h for h in get_current_holdings(account_id)}
    if set(rebuilt) != set(saved):
        return True
    for sym, lot in rebuilt.items():
        row = saved.get(sym)
        if not row:
            return True
        if abs(float(row["shares"]) - lot.shares) > 1e-4:
            return True
        if abs(float(row["avg_cost"]) - lot.avg_cost) > 0.005:
            return True
    return False


def ensure_holdings_reconciled(account_id: int = DEFAULT_ACCOUNT_ID) -> bool:
    """Repair ledger fill prices and rebuild holdings when reconstruction drifts."""
    account = get_or_create_account()
    if account.get("source") == "robinhood_mcp":
        # Live Robinhood positions are authoritative; ledger is trade history only.
        return False
    repaired = repair_ledger_fill_prices(account_id)
    drift = _holdings_drift_from_ledger(account_id)
    if repaired or drift:
        refresh_holdings_snapshot()
        return True
    return False


def import_robinhood_csv(content: str | bytes, filename: str, *, cash: float | None = None, replace: bool = False) -> dict:
    """
    Simple CSV import:
    1. Parse CSV → store all rows in the ledger (positions + misc events)
    2. Verify manual journal trades against the new CSV
    3. Rebuild holdings from the full ledger and save snapshot
    """
    rows, warnings = parse_robinhood_csv(content)
    account = get_or_create_account()
    account_id = account["id"]

    if replace:
        cleared = clear_csv_sourced_ledger(account_id)
        if cleared:
            warnings = list(warnings) + [f"Replaced {cleared} CSV ledger rows (manual journal entries kept)"]

    file_id = record_upload(account_id, filename, len(rows), 0, warnings)
    imported, skipped = upsert_ledger_rows(account_id, rows, source_file_id=file_id)
    purge_duplicate_trades(account_id)
    repair_phantom_journal_buys(account_id)

    journal_verification = _verify_journal_after_import(account_id, rows)
    for check in journal_verification:
        if check.get("status") == "missing":
            warnings.append(f"Journal #{check['trade_id']} {check['symbol']}: {check['message']}")

    rebuild = _rebuild_from_store(account_id)
    persisted = _apply_ledger_to_portfolio(
        account_id,
        rebuild,
        source="csv",
        cash_override=cash,
    )
    acct = update_account_source("csv", cash=persisted["cash"])

    mark_sync(
        account_id,
        "csv",
        trades_imported=imported,
        trades_skipped=skipped,
        message=f"Imported {imported} ledger rows from {filename}",
    )

    from data.freshness_store import clear_freshness_flag, mark_freshness_updated

    mark_freshness_updated("portfolio_holdings", source="csv_import", extra={"holdings": persisted["holdings_count"]})
    mark_freshness_updated("closed_positions", source="csv_import")
    clear_freshness_flag("portfolio_holdings", "holdings_dirty")
    clear_freshness_flag("closed_positions", "needs_refresh")

    return {
        "filename": filename,
        "trades_parsed": len(rows),
        "trades_imported": imported,
        "trades_skipped": skipped,
        "holdings_count": persisted["holdings_count"],
        "holdings": persisted["holdings"],
        "closed_positions": persisted["closed_positions"],
        "misc_events": persisted["misc_events"],
        "journal_verification": journal_verification,
        "cash": persisted["cash"],
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
        "misc_events": _misc_events_payload(rebuild.event_ledger),
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


def import_robinhood_csv_and_decide(content: str | bytes, filename: str, *, cash: float | None = None, replace: bool = False) -> dict:
    result = import_robinhood_csv(content, filename, cash=cash, replace=replace)
    if result.get("holdings_count", 0) > 0:
        try:
            from services.portfolio_decision_service import run_stored_portfolio_decision
            from data.freshness_store import mark_freshness_updated

            decision = run_stored_portfolio_decision(trigger="manual", persist=True)
            result["decision"] = model_to_dict(decision)
            mark_freshness_updated("daily_decision", source="csv_import")
            mark_freshness_updated("risk_metrics", source="csv_import")
            mark_freshness_updated("data_quality", source="csv_import")
        except Exception as exc:
            result["warnings"] = list(result.get("warnings") or []) + [f"Decision after import skipped: {exc}"]
    return result


def _dt_to_csv_dates(dt: datetime) -> tuple[str, str]:
    day = dt.strftime("%Y-%m-%d")
    return day, day


def _journal_ledger_hash(trade_id: int, leg: str) -> str:
    import hashlib

    return hashlib.sha256(f"journal-trade|{trade_id}|{leg}".encode()).hexdigest()


def is_journal_trade_synced(trade_id: int) -> bool:
    """True when the journal trade's open leg exists in the portfolio ledger."""
    from data.portfolio_store import ledger_has_row_hash

    return ledger_has_row_hash(_journal_ledger_hash(trade_id, "buy"))


def journal_trade_sync_status(*, trade_id: int, quantity: float | None) -> tuple[str, bool]:
    """Return (status, synced) for journal list UI — synced | pending | needs_quantity."""
    qty = float(quantity or 0)
    if qty <= 0:
        return "needs_quantity", False
    if is_journal_trade_synced(trade_id):
        return "synced", True
    return "pending", False


def evaluate_portfolio_sync_result(result: dict | None) -> tuple[bool, str | None]:
    """Interpret apply_manual_trade_to_portfolio output for API responses."""
    if not result:
        return False, "Portfolio sync failed"
    imported = int(result.get("imported") or 0)
    skipped = int(result.get("skipped") or 0)
    holdings_count = int(result.get("holdings_count") or 0)
    msg = str(result.get("message") or "")
    decision_error = result.get("decision_error")

    ledger_touched = imported > 0 or skipped > 0
    if decision_error:
        if ledger_touched:
            note = f"{msg} (decision refresh: {decision_error})" if msg else str(decision_error)[:200]
            return True, note[:200]
        return False, str(decision_error)[:200]
    if imported > 0:
        return True, msg or "Portfolio updated from journal trade"
    if skipped > 0:
        return True, msg or "Portfolio refreshed (trade already synced)"
    if holdings_count > 0 and msg:
        return True, msg
    return False, msg or "No ledger changes — check quantity and symbol"


def apply_manual_trade_to_portfolio(
    *,
    trade_id: int,
    symbol: str,
    side: str,
    entry_time: datetime,
    entry_price: float,
    quantity: float | None,
    exit_time: datetime | None = None,
    exit_price: float | None = None,
    notes: str = "",
) -> dict | None:
    """Append a journal/manual trade to the portfolio ledger and rebuild holdings."""
    from datetime import datetime as dt_cls

    from integrations.robinhood.models import ParsedCsvRow

    qty = float(quantity or 0)
    if qty <= 0:
        return {"imported": 0, "skipped": 0, "message": "Quantity required to update Home portfolio"}

    sym = (symbol or "").upper().strip()
    if not sym:
        return None

    account = get_or_create_account()
    account_id = account["id"]
    description = (notes or "Manual trade entry").strip()[:300]
    ledger_rows: list[ParsedCsvRow] = []

    entry_dt = entry_time.replace(tzinfo=None) if getattr(entry_time, "tzinfo", None) else entry_time
    activity, process = _dt_to_csv_dates(entry_dt)
    entry_px = float(entry_price or 0)
    has_exit = exit_price is not None and float(exit_price) > 0
    # Closed journal log with no entry price: sell only (position already from CSV).
    record_buy = not has_exit or entry_px > 0

    if record_buy:
        buy_amount = -(qty * entry_px)
        buy_hash = _journal_ledger_hash(trade_id, "buy")
        ledger_rows.append(
            ParsedCsvRow(
                activity_date=activity,
                process_date=process,
                instrument=sym,
                description=f"{description} [journal #{trade_id}]",
                trans_code="MANUAL",
                quantity=qty,
                price=entry_px,
                amount=buy_amount,
                row_type="buy",
                row_hash=buy_hash,
                executed_at=entry_dt,
            )
        )

    if has_exit:
        exit_dt = exit_time or entry_dt
        if isinstance(exit_dt, dt_cls) and exit_dt.tzinfo:
            exit_dt = exit_dt.replace(tzinfo=None)
        ex_activity, ex_process = _dt_to_csv_dates(exit_dt)
        sell_amount = qty * float(exit_price)
        sell_hash = _journal_ledger_hash(trade_id, "sell")
        ledger_rows.append(
            ParsedCsvRow(
                activity_date=ex_activity,
                process_date=ex_process,
                instrument=sym,
                description=f"{description} [journal #{trade_id}]",
                trans_code="MANUAL",
                quantity=qty,
                price=float(exit_price),
                amount=sell_amount,
                row_type="sell",
                row_hash=sell_hash,
                executed_at=exit_dt,
            )
        )

    imported, skipped = upsert_ledger_rows(account_id, ledger_rows)
    already_synced = imported == 0 and skipped > 0

    repair_phantom_journal_buys(account_id)
    purge_duplicate_trades(account_id)
    rebuild = _rebuild_from_store(account_id)
    source = account.get("source") or "manual"
    if source == "manual" and rebuild.open_holdings:
        update_account_source("csv")
        source = "csv"
    persisted = _apply_ledger_to_portfolio(account_id, rebuild, source=source)
    saved = persisted["holdings"]
    closed = persisted["closed_positions"]

    portfolio_result: dict = {
        "imported": imported,
        "skipped": skipped,
        "holdings_count": persisted["holdings_count"],
        "holdings": saved,
        "closed_positions": closed,
        "misc_events": persisted["misc_events"],
        "message": "Portfolio updated from journal trade"
        if imported > 0
        else ("Portfolio refreshed (trade already synced)" if already_synced else "No ledger changes"),
    }

    from data.freshness_store import clear_freshness_flag, mark_freshness_updated

    mark_freshness_updated("portfolio_holdings", source="manual_trade", extra={"symbol": sym})
    mark_freshness_updated("closed_positions", source="manual_trade")
    clear_freshness_flag("portfolio_holdings", "holdings_dirty")
    clear_freshness_flag("closed_positions", "needs_refresh")

    try:
        from services.portfolio_decision_service import run_stored_portfolio_decision

        decision = run_stored_portfolio_decision(trigger="manual_trade", persist=True)
        portfolio_result["decision"] = model_to_dict(decision)
        mark_freshness_updated("daily_decision", source="manual_trade")
        mark_freshness_updated("risk_metrics", source="manual_trade")
        mark_freshness_updated("data_quality", source="manual_trade")
    except Exception as exc:
        portfolio_result["decision_error"] = str(exc)[:200]

    return portfolio_result


def import_robinhood_mcp_and_decide(*, run_decision: bool = False) -> dict:
    """Pull live holdings, order history, and buying power from Robinhood MCP."""
    client = RobinhoodMcpClient()
    if not client.is_configured():
        raise ValueError(
            "Robinhood MCP not authenticated. Run: cd backend && python scripts/robinhood_mcp_login.py"
        )

    snapshot = asyncio.run(client.fetch_live_portfolio(include_orders=True))
    account = get_or_create_account()
    account_id = account["id"]

    orders_imported = 0
    orders_skipped = 0
    ledger_rebuild: PortfolioRebuildResult | None = None
    cleared_ledger = clear_trade_ledger(account_id)
    if snapshot.order_rows:
        orders_imported, orders_skipped = upsert_ledger_rows(account_id, snapshot.order_rows)
        purge_duplicate_trades(account_id)
        repair_phantom_journal_buys(account_id)
        ledger_rebuild = _rebuild_from_store(account_id)

    # Live MCP positions are the source of truth for open holdings. Rebuilding from
    # the ledger merges incomplete MCP order history with legacy CSV rows and drifts
    # away from what Robinhood reports today.
    rebuild = PortfolioRebuildResult(
        open_holdings=snapshot.holdings,
        closed_positions=ledger_rebuild.closed_positions if ledger_rebuild else [],
        cash_delta=snapshot.buying_power,
        event_ledger=ledger_rebuild.event_ledger if ledger_rebuild else [],
        excluded_rows=[],
        unknown_trans_codes=[],
        warnings=(
            ["Holdings from live Robinhood positions; trade history replaced on each MCP sync"]
            if snapshot.order_rows
            else (
                [f"Cleared {cleared_ledger} stale ledger rows; no MCP order history returned"]
                if cleared_ledger
                else ["No MCP order history returned — using live positions only"]
            )
        ),
    )

    persisted = _apply_ledger_to_portfolio(
        account_id,
        rebuild,
        source="robinhood_mcp",
        cash_override=snapshot.buying_power,
    )
    acct = update_account_source("robinhood_mcp", cash=persisted["cash"])
    mark_sync(
        account_id,
        "robinhood_mcp",
        trades_imported=orders_imported,
        trades_skipped=orders_skipped,
        message=f"MCP sync: {persisted['holdings_count']} positions, {orders_imported} order rows",
    )

    from data.freshness_store import clear_freshness_flag, mark_freshness_updated

    mark_freshness_updated(
        "portfolio_holdings",
        source="robinhood_mcp",
        extra={"holdings": persisted["holdings_count"]},
    )
    clear_freshness_flag("portfolio_holdings", "holdings_dirty")

    result = {
        "holdings_count": persisted["holdings_count"],
        "holdings": persisted["holdings"],
        "cash": persisted["cash"],
        "portfolio_value": snapshot.portfolio_value,
        "account_id": snapshot.account_id,
        "robinhood_account_number": snapshot.account_id,
        "data_source": "robinhood_mcp",
        "orders_imported": orders_imported,
        "orders_skipped": orders_skipped,
        "ledger_rows_count": len(snapshot.order_rows),
        "account": acct,
    }

    if run_decision and persisted["holdings_count"] >= 0:
        try:
            from services.portfolio_decision_service import run_stored_portfolio_decision

            decision = run_stored_portfolio_decision(trigger="robinhood_mcp", persist=True)
            result["decision"] = model_to_dict(decision)
            mark_freshness_updated("daily_decision", source="robinhood_mcp")
        except Exception as exc:
            result["decision_error"] = str(exc)[:200]

    return result


def robinhood_mcp_status() -> dict:
    client = RobinhoodMcpClient()
    return {
        "enabled": bool(os.getenv("ROBINHOOD_MCP_ENABLED", "true").strip().lower() not in ("0", "false", "no", "off")),
        "authenticated": client.is_configured(),
        "endpoint": os.getenv("ROBINHOOD_MCP_URL", "https://agent.robinhood.com/mcp/trading"),
    }


def sync_brokerage_if_configured() -> dict:
    mcp = RobinhoodMcpClient()
    if mcp.is_configured():
        try:
            result = import_robinhood_mcp_and_decide(run_decision=False)
            return {
                "synced": True,
                "source": "robinhood_mcp",
                "holdings_count": result.get("holdings_count", 0),
                "orders_imported": result.get("orders_imported", 0),
                "message": (
                    f"MCP sync: {result.get('holdings_count', 0)} positions, "
                    f"{result.get('orders_imported', 0)} order rows"
                ),
            }
        except Exception as exc:
            logger.exception("Robinhood MCP auto-sync failed")
            return {"synced": False, "source": "robinhood_mcp", "message": str(exc)[:200]}

    snap = SnapTradeClient()
    if not snap.is_configured():
        return {
            "synced": False,
            "source": get_or_create_account().get("source", "manual"),
            "message": "No live brokerage sync configured — run robinhood_mcp_login.py",
        }
    result = snap.sync_holdings()
    return {"synced": False, "source": "snaptrade", "message": result.message}


def refresh_holdings_snapshot() -> dict:
    account = get_or_create_account()
    if account.get("source") == "robinhood_mcp":
        snap = get_latest_portfolio_snapshot()
        holdings = get_current_holdings()
        cash = get_account_cash()
        return {
            "holdings": holdings,
            "cash": cash,
            "closed_positions": (snap or {}).get("closed_positions") or [],
            "misc_events": (snap or {}).get("misc_events") or [],
            "snapshot": snap or {},
            "duplicates_removed": 0,
            "phantom_buys_removed": 0,
            "prices_repaired": 0,
            "skipped_ledger_rebuild": True,
        }
    repaired = repair_ledger_fill_prices(DEFAULT_ACCOUNT_ID)
    removed_phantoms = repair_phantom_journal_buys(DEFAULT_ACCOUNT_ID)
    removed = purge_duplicate_trades(DEFAULT_ACCOUNT_ID)
    rebuild = _rebuild_from_store()
    cash = get_account_cash()
    persisted = _apply_ledger_to_portfolio(
        DEFAULT_ACCOUNT_ID,
        rebuild,
        source=account["source"],
        cash_override=cash,
    )
    snap = get_latest_portfolio_snapshot()
    return {
        "holdings": persisted["holdings"],
        "cash": persisted["cash"],
        "closed_positions": persisted["closed_positions"],
        "misc_events": persisted["misc_events"],
        "snapshot": snap or {},
        "duplicates_removed": removed,
        "phantom_buys_removed": removed_phantoms,
        "prices_repaired": repaired,
    }


def estimate_ledger_cash(account_id: int = DEFAULT_ACCOUNT_ID) -> float:
    """Uninvested cash reconstructed from CSV ledger (deposits − buys + sells)."""
    rows = load_all_ledger_rows(account_id)
    if not rows:
        return 0.0
    return max(0.0, rebuild_portfolio(rows).cash_delta)


def resolve_portfolio_cash(account_id: int = DEFAULT_ACCOUNT_ID) -> tuple[float, str]:
    """
    Robinhood buying power — uninvested cash available to trade.
    Does not include reserved IPO cash (see reserved_cash on account).
    """
    acct = get_or_create_account()
    stored = float(acct.get("cash_balance") or 0)
    source = acct.get("source", "manual")
    if stored > 0:
        return stored, "buying_power"
    if source == "csv":
        ledger = estimate_ledger_cash(account_id)
        reserved = float(acct.get("reserved_cash") or 0)
        # Ledger cash may include reserved IPO; subtract if both set via import
        if ledger > 0 and reserved > 0:
            return max(0.0, ledger - reserved), "ledger"
        if ledger > 0:
            return ledger, "ledger"
    return stored, "buying_power"


def get_reserved_cash(account_id: int = DEFAULT_ACCOUNT_ID) -> float:
    return get_account_reserved_cash(account_id)


def set_portfolio_cash(
    *,
    buying_power: float,
    reserved_cash: float = 0,
    ipo_shares: float | None = None,
    ipo_list_price: float | None = None,
    account_id: int = DEFAULT_ACCOUNT_ID,
) -> dict:
    """Set buying power and optional reserved cash (e.g. upcoming IPO)."""
    from integrations.robinhood.ipo import ROBINHOOD_IPO_BUFFER, compute_ipo_reserved_cash

    reserved = max(0.0, float(reserved_cash))
    shares = float(ipo_shares) if ipo_shares is not None else None
    list_price = float(ipo_list_price) if ipo_list_price is not None else None
    if shares is not None and list_price is not None and shares > 0 and list_price > 0:
        reserved = compute_ipo_reserved_cash(shares=shares, list_price=list_price)

    set_account_cash(account_id, max(0.0, float(buying_power)))
    set_account_ipo_order(
        account_id,
        shares=shares if shares and shares > 0 else None,
        list_price=list_price if list_price and list_price > 0 else None,
        reserved=reserved,
    )
    acct = get_or_create_account()
    return {
        "cash": float(acct.get("cash_balance") or 0),
        "reserved_cash": float(acct.get("reserved_cash") or 0),
        "ipo_shares": acct.get("ipo_shares"),
        "ipo_list_price": acct.get("ipo_list_price"),
        "ipo_buffer": ROBINHOOD_IPO_BUFFER,
        "account": acct,
    }


def set_buying_power(cash: float, *, account_id: int = DEFAULT_ACCOUNT_ID) -> dict:
    """Set uninvested cash / buying power (Robinhood unused cash in total portfolio)."""
    cash = max(0.0, float(cash))
    set_account_cash(account_id, cash)
    acct = get_or_create_account()
    return {"cash": cash, "account": acct}


def holdings_to_request() -> tuple[float, float, list[PortfolioHolding]]:
    cash, _ = resolve_portfolio_cash()
    reserved = get_reserved_cash()
    rows = get_current_holdings()
    holdings = [
        PortfolioHolding(
            symbol=r["symbol"],
            shares=r["shares"],
            avg_cost=r["avg_cost"],
            bucket=normalize_bucket(r["bucket"]),
        )
        for r in rows
    ]
    return cash, reserved, holdings


def get_current_portfolio() -> dict:
    ensure_holdings_reconciled()
    account = get_or_create_account()
    holdings = get_current_holdings()
    snap = get_latest_portfolio_snapshot()
    closed = (snap or {}).get("closed_positions") or []
    misc_events = (snap or {}).get("misc_events") or []
    cash, cash_source = resolve_portfolio_cash()
    reserved_cash = get_reserved_cash()
    return {
        "account": account,
        "cash": cash,
        "cash_source": cash_source,
        "reserved_cash": reserved_cash,
        "ipo_shares": account.get("ipo_shares"),
        "ipo_list_price": account.get("ipo_list_price"),
        "holdings": holdings,
        "closed_positions": closed,
        "misc_events": misc_events,
        "data_source": account["source"],
        "is_demo_data": account["source"] == "demo",
    }


def list_import_history() -> list[dict]:
    return list_uploads()
