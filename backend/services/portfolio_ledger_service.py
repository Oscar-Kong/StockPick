"""Portfolio ledger CRUD, CSV preview, and approved import."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from data.portfolio_store import (
    DEFAULT_ACCOUNT_ID,
    clear_csv_sourced_ledger,
    delete_ledger_row,
    get_ledger_row,
    get_or_create_account,
    insert_ledger_row,
    list_ledger_rows_detailed,
    mark_sync,
    purge_duplicate_trades,
    record_upload,
    repair_phantom_journal_buys,
    set_ledger_row_locked,
    update_ledger_row,
    upsert_ledger_rows,
)
from integrations.robinhood.csv_importer import _parse_datetime, parse_robinhood_csv, row_hash_from_fields
from integrations.robinhood.models import ParsedCsvRow, normalize_row_type
from integrations.robinhood.portfolio_rebuilder import rebuild_portfolio
from services.portfolio_snapshot_service import (
    _apply_ledger_to_portfolio,
    _misc_events_payload,
    _rebuild_from_store,
)


def _ledger_source(trans_code: str | None, source_file_id: int | None) -> str:
    tc = (trans_code or "").upper()
    if tc == "MANUAL":
        return "journal"
    if source_file_id is not None:
        return "csv"
    return "manual"


def _ledger_row_sort_key(row: dict) -> tuple[float, int]:
    """Newest activity first (Robinhood M/D/YYYY dates parsed chronologically)."""
    dt: datetime | None = None
    executed = row.get("executed_at")
    if executed:
        try:
            dt = datetime.fromisoformat(str(executed).replace("Z", "+00:00"))
        except ValueError:
            dt = None
    if dt is None:
        dt = _parse_datetime(row.get("activity_date") or "", row.get("process_date") or "")
    ts = dt.timestamp() if dt else 0.0
    return (ts, int(row.get("id") or 0))


def _row_to_api(row: dict) -> dict[str, Any]:
    side = (row.get("side") or "").lower()
    row_type = normalize_row_type(side if side in ("buy", "sell", "event", "cash", "income") else "event")
    return {
        "id": row["id"],
        "symbol": row.get("symbol") or "",
        "side": side,
        "row_type": row_type,
        "quantity": row.get("quantity"),
        "price": row.get("price"),
        "amount": row.get("amount"),
        "trans_code": row.get("trans_code"),
        "description": row.get("description"),
        "activity_date": row.get("activity_date"),
        "process_date": row.get("process_date"),
        "executed_at": row.get("executed_at"),
        "source": _ledger_source(row.get("trans_code"), row.get("source_file_id")),
        "row_hash": row.get("row_hash"),
        "locked": bool(row.get("locked")),
    }


def list_ledger_api(account_id: int = DEFAULT_ACCOUNT_ID) -> dict[str, Any]:
    raw_rows = list_ledger_rows_detailed(account_id)
    raw_rows.sort(key=_ledger_row_sort_key, reverse=True)
    rows = [_row_to_api(r) for r in raw_rows]
    rebuild = _rebuild_from_store(account_id)
    return {
        "rows": rows,
        "open_holdings": [
            {
                "symbol": h.symbol,
                "shares": h.shares,
                "avg_cost": h.avg_cost,
                "bucket": h.bucket,
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
        "ledger_cash_estimate": rebuild.cash_delta,
        "warnings": rebuild.warnings,
    }


def _parsed_from_input(data: dict[str, Any], *, row_id: int | None = None) -> ParsedCsvRow:
    side = (data.get("side") or data.get("row_type") or "buy").lower()
    if side in ("cash", "income"):
        side = "event"
    row_type = normalize_row_type(side)
    symbol = (data.get("symbol") or "").upper().strip()
    qty = data.get("quantity")
    price = data.get("price")
    amount = float(data.get("amount") or 0)
    activity = (data.get("activity_date") or "").strip()
    process = (data.get("process_date") or activity).strip()
    trans_code = (data.get("trans_code") or side.upper()).upper()
    description = (data.get("description") or "")[:300]

    if row_type in ("buy", "sell"):
        q = abs(float(qty or 0))
        p = float(price or 0)
        if amount == 0 and q > 0 and p > 0:
            amount = q * p if row_type == "sell" else -(q * p)
    elif amount == 0:
        amount = float(data.get("amount") or 0)

    rh = data.get("row_hash")
    if not rh:
        rh = row_hash_from_fields(
            activity_date=activity,
            process_date=process,
            instrument=symbol,
            trans_code=trans_code,
            quantity=float(qty) if qty is not None else None,
            price=float(price) if price is not None else None,
            amount=amount,
            description=description,
        )
    if row_id is not None:
        rh = f"{rh}|ledger-{row_id}"

    executed = None
    for raw in (activity, process):
        if not raw:
            continue
        for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y-%m-%d %H:%M:%S", "%m/%d/%Y %H:%M:%S"):
            try:
                executed = datetime.strptime(str(raw).strip()[:19], fmt)
                break
            except ValueError:
                continue
        if executed:
            break

    return ParsedCsvRow(
        activity_date=activity,
        process_date=process,
        instrument=symbol,
        description=description,
        trans_code=trans_code,
        quantity=float(qty) if qty is not None else None,
        price=float(price) if price is not None else None,
        amount=amount,
        row_type=row_type,
        row_hash=rh,
        executed_at=executed,
    )


def _rebuild_account(account_id: int, *, source: str = "csv", cash: float | None = None) -> dict:
    repair_phantom_journal_buys(account_id)
    purge_duplicate_trades(account_id)
    rebuild = _rebuild_from_store(account_id)
    return _apply_ledger_to_portfolio(account_id, rebuild, source=source, cash_override=cash)


def create_ledger_entry(data: dict[str, Any], account_id: int = DEFAULT_ACCOUNT_ID) -> dict[str, Any]:
    parsed = _parsed_from_input(data)
    row_id = insert_ledger_row(account_id, parsed, trans_code_override=(data.get("trans_code") or "MANUAL").upper())
    _rebuild_account(account_id)
    row = get_ledger_row(row_id)
    return _row_to_api(row) if row else {}


def update_ledger_entry(row_id: int, data: dict[str, Any], account_id: int = DEFAULT_ACCOUNT_ID) -> dict[str, Any]:
    existing = get_ledger_row(row_id)
    if not existing:
        raise ValueError("Ledger row not found")
    if existing.get("locked"):
        raise ValueError("Ledger row is locked")
    lock = bool(data.pop("lock", False))
    merged = {**existing, **{k: v for k, v in data.items() if k != "lock" and (v is not None or k in data)}}
    parsed = _parsed_from_input(merged, row_id=row_id)
    update_ledger_row(row_id, parsed)
    if lock:
        set_ledger_row_locked(row_id, True, account_id)
    _rebuild_account(account_id)
    row = get_ledger_row(row_id)
    return _row_to_api(row) if row else {}


def remove_ledger_entry(row_id: int, account_id: int = DEFAULT_ACCOUNT_ID) -> None:
    existing = get_ledger_row(row_id)
    if existing and existing.get("locked"):
        raise ValueError("Ledger row is locked")
    if not delete_ledger_row(row_id, account_id):
        raise ValueError("Ledger row not found")
    _rebuild_account(account_id)


def rebuild_ledger_holdings(account_id: int = DEFAULT_ACCOUNT_ID) -> dict[str, Any]:
    persisted = _rebuild_account(account_id)
    return {
        "holdings_count": persisted["holdings_count"],
        "holdings": persisted["holdings"],
        "closed_positions": persisted["closed_positions"],
        "cash": persisted["cash"],
    }


def preview_robinhood_csv(content: str | bytes, filename: str, *, replace: bool = False) -> dict[str, Any]:
    parsed_rows, warnings = parse_robinhood_csv(content)
    account = get_or_create_account()
    account_id = account["id"]
    existing_hashes = {r.get("row_hash") for r in list_ledger_rows_detailed(account_id)}

    preview_rows: list[dict[str, Any]] = []
    included_parsed: list[ParsedCsvRow] = []
    for row in parsed_rows:
        is_new = row.row_hash not in existing_hashes
        preview_rows.append(
            {
                "client_id": str(uuid.uuid4()),
                "included": True,
                "is_new": is_new,
                "symbol": row.instrument or "",
                "side": row.row_type if row.row_type != "event" else "event",
                "row_type": normalize_row_type(row.row_type),
                "quantity": row.quantity,
                "price": row.price,
                "amount": row.amount,
                "trans_code": row.trans_code,
                "description": row.description,
                "activity_date": row.activity_date,
                "process_date": row.process_date,
                "row_hash": row.row_hash,
            }
        )
        included_parsed.append(row)

    current_parsed = [
        _parsed_from_input(r)
        for r in list_ledger_rows_detailed(account_id)
    ]
    current_rebuild = rebuild_portfolio(current_parsed) if current_parsed else rebuild_portfolio([])

    if replace:
        projection_input = included_parsed
    else:
        new_only = [r for r in parsed_rows if r.row_hash not in existing_hashes]
        projection_input = current_parsed + new_only

    rebuild = rebuild_portfolio(projection_input)

    return {
        "filename": filename,
        "rows": preview_rows,
        "warnings": warnings,
        "current_holdings": [
            {"symbol": h.symbol, "shares": h.shares, "avg_cost": h.avg_cost}
            for h in current_rebuild.open_holdings
        ],
        "projected_holdings": [
            {"symbol": h.symbol, "shares": h.shares, "avg_cost": h.avg_cost}
            for h in rebuild.open_holdings
        ],
        "current_cash_estimate": current_rebuild.cash_delta,
        "projected_cash_estimate": rebuild.cash_delta,
        "new_row_count": sum(1 for r in preview_rows if r["is_new"]),
        "skipped_existing_count": sum(1 for r in preview_rows if not r["is_new"]),
    }


def approve_csv_import(
    *,
    filename: str,
    rows: list[dict[str, Any]],
    replace: bool = False,
    cash: float | None = None,
) -> dict[str, Any]:
    """Persist user-reviewed CSV rows and rebuild portfolio."""
    account = get_or_create_account()
    account_id = account["id"]

    if replace:
        clear_csv_sourced_ledger(account_id)

    parsed: list[ParsedCsvRow] = []
    for item in rows:
        if item.get("included") is False:
            continue
        parsed.append(_parsed_from_input(item))

    if not parsed and not replace:
        raise ValueError("No rows selected for import")

    file_id = record_upload(account_id, filename, len(parsed), 0, [])
    imported, skipped = upsert_ledger_rows(account_id, parsed, source_file_id=file_id)
    repair_phantom_journal_buys(account_id)
    purge_duplicate_trades(account_id)
    persisted = _rebuild_account(account_id, cash=cash)

    mark_sync(
        account_id,
        "csv",
        trades_imported=imported,
        trades_skipped=skipped,
        message=f"Approved import of {imported} rows from {filename}",
    )

    result = {
        "filename": filename,
        "trades_parsed": len(rows),
        "trades_imported": imported,
        "trades_skipped": skipped,
        "holdings_count": persisted["holdings_count"],
        "holdings": persisted["holdings"],
        "closed_positions": persisted["closed_positions"],
        "misc_events": persisted.get("misc_events") or _misc_events_payload(_rebuild_from_store(account_id).event_ledger),
        "warnings": [],
        "account": get_or_create_account(),
    }

    if persisted["holdings_count"] > 0:
        try:
            from services.portfolio_decision_service import run_stored_portfolio_decision
            from data.freshness_store import mark_freshness_updated
            from utils.pydantic_util import model_to_dict

            decision = run_stored_portfolio_decision(trigger="manual", persist=True)
            result["decision"] = model_to_dict(decision)
            mark_freshness_updated("daily_decision", source="csv_import")
            mark_freshness_updated("portfolio_holdings", source="csv_import")
            mark_freshness_updated("closed_positions", source="csv_import")
        except Exception as exc:
            result["warnings"] = [f"Decision after import skipped: {exc}"]

    return result
