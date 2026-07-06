"""Parse Robinhood MCP filled equity orders into ledger rows."""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any

from integrations.robinhood.models import ParsedCsvRow

logger = logging.getLogger(__name__)

MCP_MAX_ORDER_PAGES = 20


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is not None:
            return dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    except ValueError:
        return None


def _date_str(dt: datetime | None) -> str:
    if dt is None:
        return ""
    return dt.strftime("%m/%d/%Y")


def _iter_orders(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        out: list[dict[str, Any]] = []
        for item in payload:
            out.extend(_iter_orders(item))
        return out
    if not isinstance(payload, dict):
        return []
    if isinstance(payload.get("orders"), list):
        return [o for o in payload["orders"] if isinstance(o, dict)]
    for key in ("data", "results", "items"):
        if key in payload:
            found = _iter_orders(payload[key])
            if found:
                return found
    return []


def _order_cursor(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    for key in ("cursor", "next_cursor"):
        val = payload.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    data = payload.get("data")
    if isinstance(data, dict):
        for key in ("cursor", "next_cursor"):
            val = data.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
    return None


def parse_mcp_equity_orders(payload: Any) -> list[ParsedCsvRow]:
    """Convert filled MCP equity order executions into ledger-compatible rows."""
    rows: list[ParsedCsvRow] = []
    for order in _iter_orders(payload):
        state = str(order.get("state") or "").lower()
        if state and state not in ("filled", "partially_filled"):
            continue
        side = str(order.get("side") or "").lower()
        if side not in ("buy", "sell"):
            continue
        symbol = str(order.get("symbol") or "").upper().strip()
        if not symbol:
            continue

        order_type = str(order.get("type") or "market")
        placed_agent = str(order.get("placed_agent") or "user")
        order_id = str(order.get("id") or "")
        executions = order.get("executions")
        if not isinstance(executions, list) or not executions:
            qty = _float(order.get("cumulative_quantity") or order.get("quantity"))
            price = _float(order.get("average_price") or order.get("price"))
            ts = _parse_ts(order.get("last_transaction_at") or order.get("created_at"))
            if qty and price:
                executions = [
                    {
                        "id": order_id or f"{symbol}-{side}-{ts}",
                        "quantity": qty,
                        "price": price,
                        "timestamp": order.get("last_transaction_at") or order.get("created_at"),
                    }
                ]
            else:
                continue

        for ex in executions:
            if not isinstance(ex, dict):
                continue
            qty = _float(ex.get("quantity"))
            price = _float(ex.get("price") or order.get("average_price"))
            if not qty or not price:
                continue
            executed_at = _parse_ts(ex.get("timestamp") or order.get("last_transaction_at") or order.get("created_at"))
            activity_date = _date_str(executed_at)
            amount = round(qty * price * (-1 if side == "buy" else 1), 4)
            exec_id = str(ex.get("id") or order_id or f"{symbol}-{side}-{activity_date}-{qty}")
            trans_code = "MCP-BUY" if side == "buy" else "MCP-SELL"
            description = f"Robinhood {order_type} {side} ({placed_agent})"
            row_hash = hashlib.sha256(f"robinhood-mcp-exec:{exec_id}".encode()).hexdigest()
            rows.append(
                ParsedCsvRow(
                    activity_date=activity_date,
                    process_date=activity_date,
                    instrument=symbol,
                    description=description,
                    trans_code=trans_code,
                    quantity=qty,
                    price=price,
                    amount=amount,
                    row_type=side,  # type: ignore[arg-type]
                    row_hash=row_hash,
                    executed_at=executed_at,
                    raw={"order_id": order_id, "execution_id": exec_id, "order": order, "execution": ex},
                )
            )
    return rows


def _float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None
