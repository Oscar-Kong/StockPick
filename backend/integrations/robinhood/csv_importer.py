"""Robinhood transaction CSV parser."""
from __future__ import annotations

import csv
import hashlib
import io
import re
from datetime import datetime

from integrations.robinhood.models import ParsedTrade

_SYMBOL_RE = re.compile(r"^[A-Z][A-Z0-9.\-]{0,9}$")

_HEADER_ALIASES: dict[str, tuple[str, ...]] = {
    "symbol": ("instrument", "ticker", "symbol", "stock symbol"),
    "side": ("trans code", "type", "side", "action", "transaction type"),
    "quantity": ("quantity", "qty", "shares"),
    "price": ("price", "fill price", "average price"),
    "fees": ("fees", "fee", "commission"),
    "executed_at": ("activity date", "date", "trade date", "execution time", "process date"),
    "order_id": ("order id", "order_id", "id"),
    "amount": ("amount", "net amount"),
}


def _norm_header(h: str) -> str:
    return h.strip().lower().replace("_", " ")


def _map_headers(fieldnames: list[str]) -> dict[str, str]:
    normalized = {_norm_header(f): f for f in fieldnames if f}
    mapping: dict[str, str] = {}
    for key, aliases in _HEADER_ALIASES.items():
        for alias in aliases:
            if alias in normalized:
                mapping[key] = normalized[alias]
                break
    return mapping


def _parse_side(raw: str) -> str:
    val = (raw or "").strip().lower()
    if val in ("buy", "b", "purchase", "purch", "cdiv", "splt"):  # splt often paired with shares in
        if "sell" in val or val in ("sell", "s", "sale"):
            return "sell"
        return "buy"
    if val in ("sell", "s", "sale", "sto", "btc"):
        return "sell"
    if "sell" in val:
        return "sell"
    if "buy" in val:
        return "buy"
    return "buy"


def _parse_float(val: str | None) -> float:
    if val is None:
        return 0.0
    s = str(val).strip().replace("$", "").replace(",", "")
    if not s or s == "--":
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def _parse_datetime(val: str | None) -> datetime | None:
    if not val:
        return None
    s = str(val).strip()
    for fmt in (
        "%Y-%m-%d",
        "%m/%d/%Y",
        "%Y-%m-%d %H:%M:%S",
        "%m/%d/%Y %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
    ):
        try:
            return datetime.strptime(s[:19], fmt)
        except ValueError:
            continue
    return None


def _extract_symbol(row: dict, mapping: dict[str, str]) -> str | None:
    sym_col = mapping.get("symbol")
    if sym_col and row.get(sym_col):
        sym = str(row[sym_col]).strip().upper()
        if _SYMBOL_RE.match(sym):
            return sym
    desc = row.get("Description") or row.get("description") or ""
    m = re.search(r"\b([A-Z]{1,5})\b", str(desc).upper())
    if m and _SYMBOL_RE.match(m.group(1)):
        return m.group(1)
    return None


def trade_row_hash(
    *,
    symbol: str,
    side: str,
    quantity: float,
    price: float,
    executed_at: datetime | None,
    order_id: str | None,
) -> str:
    ts = executed_at.isoformat() if executed_at else ""
    oid = order_id or ""
    payload = f"{ts}|{symbol}|{side}|{quantity}|{price}|{oid}"
    return hashlib.sha256(payload.encode()).hexdigest()


def parse_robinhood_csv(content: str | bytes) -> tuple[list[ParsedTrade], list[str]]:
    """Parse Robinhood export CSV; returns trades and parse warnings."""
    warnings: list[str] = []
    if isinstance(content, bytes):
        text = content.decode("utf-8-sig", errors="replace")
    else:
        text = content

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        return [], ["Empty CSV or missing header row"]

    mapping = _map_headers(list(reader.fieldnames))
    if "symbol" not in mapping and "quantity" not in mapping:
        warnings.append("Unrecognized CSV columns — attempting best-effort parse")

    trades: list[ParsedTrade] = []
    for i, row in enumerate(reader, start=2):
        sym = _extract_symbol(row, mapping)
        if not sym:
            continue

        side_col = mapping.get("side")
        side_raw = row.get(side_col, "") if side_col else ""
        side = _parse_side(side_raw)

        qty_col = mapping.get("quantity")
        qty = abs(_parse_float(row.get(qty_col) if qty_col else None))
        if qty <= 0:
            continue

        price_col = mapping.get("price")
        price = _parse_float(row.get(price_col) if price_col else None)
        if price <= 0:
            amt_col = mapping.get("amount")
            if amt_col:
                amt = abs(_parse_float(row.get(amt_col)))
                if amt > 0 and qty > 0:
                    price = amt / qty

        fees_col = mapping.get("fees")
        fees = _parse_float(row.get(fees_col) if fees_col else None)

        dt_col = mapping.get("executed_at")
        executed_at = _parse_datetime(row.get(dt_col) if dt_col else None)

        oid_col = mapping.get("order_id")
        order_id = str(row.get(oid_col)).strip() if oid_col and row.get(oid_col) else None

        # Skip non-trade rows (dividends without quantity, etc.)
        trans = (side_raw or "").lower()
        if trans in ("div", "int", "fee", "ach", "xfer") and qty <= 0:
            continue

        rh = trade_row_hash(
            symbol=sym,
            side=side,
            quantity=qty,
            price=price,
            executed_at=executed_at,
            order_id=order_id,
        )
        trades.append(
            ParsedTrade(
                symbol=sym,
                side=side,
                quantity=qty,
                price=price,
                fees=fees,
                executed_at=executed_at,
                order_id=order_id,
                row_hash=rh,
                raw=dict(row),
            )
        )

    if not trades:
        warnings.append("No buy/sell trades found in CSV")
    return trades, warnings
