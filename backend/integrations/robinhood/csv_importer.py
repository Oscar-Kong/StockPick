"""Robinhood transaction CSV parser — robust quoting, trans codes, signed amounts."""
from __future__ import annotations

import csv
import hashlib
import io
import logging
import re
from datetime import datetime

from integrations.robinhood.models import ParsedCsvRow, RowType

logger = logging.getLogger(__name__)

_SYMBOL_RE = re.compile(r"^[A-Z][A-Z0-9.\-]{0,9}$")

# Robinhood Trans Code → internal row type
_CASH_CODES = frozenset({"RTP", "ACH", "XACH", "XFER", "TRANSFER", "INSTANT", "DEP", "DEPOSIT", "WDL", "WITHDRAW"})
_INCOME_CODES = frozenset({"SLIP", "CDIV", "DIV", "INT", "INTEREST", "GOLD", "MISC"})
_BUY_CODES = frozenset({"BUY", "BTO", "BTC", "REINVEST", "SPLT"})
_SELL_CODES = frozenset({"SELL", "STC", "STO"})


def _norm_header(h: str) -> str:
    return h.strip().lower().replace("_", " ")


def _parse_amount(val: str | None) -> float:
    """Parse Robinhood dollar strings: $21.24, ($39.00), -39.00."""
    if val is None:
        return 0.0
    s = str(val).strip()
    if not s or s in ("--", "N/A"):
        return 0.0
    negative = s.startswith("(") and s.endswith(")")
    s = s.strip("()").replace("$", "").replace(",", "").strip()
    if not s:
        return 0.0
    try:
        n = float(s)
    except ValueError:
        return 0.0
    if negative:
        n = -abs(n)
    return n


def _parse_optional_float(val: str | None) -> float | None:
    if val is None:
        return None
    s = str(val).strip().replace("$", "").replace(",", "")
    if not s or s == "--":
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _parse_datetime(activity: str, process: str) -> datetime | None:
    for raw in (activity, process):
        if not raw:
            continue
        s = str(raw).strip()
        for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y-%m-%d %H:%M:%S", "%m/%d/%Y %H:%M:%S"):
            try:
                return datetime.strptime(s[:19], fmt)
            except ValueError:
                continue
    return None


def _classify_trans_code(code: str) -> RowType:
    c = (code or "").strip().upper()
    if not c:
        return "excluded"
    if c in _BUY_CODES or c == "BUY":
        return "buy"
    if c in _SELL_CODES or c == "SELL":
        return "sell"
    if c in _CASH_CODES or "RTP" in c or "ACH" in c:
        return "cash"
    if c in _INCOME_CODES:
        return "income"
    # Partial match
    if "BUY" in c:
        return "buy"
    if "SELL" in c:
        return "sell"
    return "excluded"


def row_hash_from_fields(
    *,
    activity_date: str,
    process_date: str,
    instrument: str,
    trans_code: str,
    quantity: float | None,
    price: float | None,
    amount: float,
    description: str,
) -> str:
    payload = "|".join(
        [
            activity_date,
            process_date,
            instrument.upper(),
            trans_code.upper(),
            "" if quantity is None else f"{quantity:.8f}",
            "" if price is None else f"{price:.8f}",
            f"{amount:.4f}",
            (description or "")[:300],
        ]
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def _extract_symbol(instrument: str, description: str) -> str:
    inst = (instrument or "").strip().upper()
    if inst and _SYMBOL_RE.match(inst):
        return inst
    # First line of multiline description often has company name; instrument column is authoritative when set
    return ""


def parse_robinhood_csv(content: str | bytes) -> tuple[list[ParsedCsvRow], list[str]]:
    """Parse Robinhood CSV using Python csv module (handles quoted multiline fields)."""
    warnings: list[str] = []
    unknown_codes: set[str] = set()

    if isinstance(content, bytes):
        text = content.decode("utf-8-sig", errors="replace")
    else:
        text = content

    reader = csv.DictReader(io.StringIO(text, newline=""))
    if not reader.fieldnames:
        return [], ["Empty CSV or missing header row"]

    # Normalize header keys for lookup
    field_map = {_norm_header(f): f for f in reader.fieldnames if f}

    def col(*names: str) -> str | None:
        for n in names:
            key = _norm_header(n)
            if key in field_map:
                return field_map[key]
        return None

    c_activity = col("Activity Date", "activity date")
    c_process = col("Process Date", "process date")
    c_settle = col("Settle Date", "settle date")
    c_instrument = col("Instrument", "instrument")
    c_description = col("Description", "description")
    c_trans = col("Trans Code", "trans code", "type")
    c_qty = col("Quantity", "quantity")
    c_price = col("Price", "price")
    c_amount = col("Amount", "amount")

    if not c_trans:
        return [], ["Missing Trans Code column"]

    rows: list[ParsedCsvRow] = []
    for line_no, raw_row in enumerate(reader, start=2):
        trans_raw = (raw_row.get(c_trans) or "").strip()
        trans_upper = trans_raw.upper()
        row_type = _classify_trans_code(trans_upper)

        activity = (raw_row.get(c_activity) or "").strip() if c_activity else ""
        process = (raw_row.get(c_process) or "").strip() if c_process else ""
        settle = (raw_row.get(c_settle) or "").strip() if c_settle else ""
        instrument = (raw_row.get(c_instrument) or "").strip() if c_instrument else ""
        description = (raw_row.get(c_description) or "").strip() if c_description else ""

        qty = _parse_optional_float(raw_row.get(c_qty) if c_qty else None)
        price = _parse_optional_float(raw_row.get(c_price) if c_price else None)
        amount = _parse_amount(raw_row.get(c_amount) if c_amount else None)

        if row_type == "excluded" and trans_upper:
            unknown_codes.add(trans_upper)
            logger.info("Unknown Trans Code at line %s: %s", line_no, trans_upper)
            continue

        symbol = _extract_symbol(instrument, description)

        if row_type in ("buy", "sell"):
            if not symbol:
                warnings.append(f"Line {line_no}: {trans_upper} missing instrument — skipped")
                continue
            if qty is None or qty == 0:
                # derive qty from amount/price when possible
                if price and price > 0 and amount != 0:
                    qty = abs(amount / price)
                else:
                    warnings.append(f"Line {line_no}: {symbol} {trans_upper} missing quantity — skipped")
                    continue
            qty = abs(qty)
            if price is None or price <= 0:
                if qty > 0 and amount != 0:
                    price = abs(amount / qty)
                else:
                    warnings.append(f"Line {line_no}: {symbol} {trans_upper} missing price — skipped")
                    continue

        rh = row_hash_from_fields(
            activity_date=activity,
            process_date=process,
            instrument=symbol or instrument,
            trans_code=trans_upper,
            quantity=qty,
            price=price,
            amount=amount,
            description=description,
        )

        rows.append(
            ParsedCsvRow(
                activity_date=activity,
                process_date=process,
                settle_date=settle,
                instrument=symbol or instrument,
                description=description,
                trans_code=trans_upper,
                quantity=qty,
                price=price,
                amount=amount,
                row_type=row_type,
                row_hash=rh,
                executed_at=_parse_datetime(activity, process),
                raw=dict(raw_row),
            )
        )

    if unknown_codes:
        warnings.append(f"Unknown Trans Codes logged: {', '.join(sorted(unknown_codes))}")

    if not rows:
        warnings.append("No recognized rows in CSV")

    return rows, warnings


def ledger_rows_to_trades(rows: list[ParsedCsvRow]) -> list:
    """Convert buy/sell rows to ParsedTrade for storage."""
    from integrations.robinhood.models import ParsedTrade

    out: list[ParsedTrade] = []
    for r in rows:
        if r.row_type not in ("buy", "sell"):
            continue
        out.append(
            ParsedTrade(
                symbol=r.instrument.upper(),
                side=r.row_type,
                quantity=float(r.quantity or 0),
                price=float(r.price or 0),
                executed_at=r.executed_at,
                row_hash=r.row_hash,
                trans_code=r.trans_code,
                amount=r.amount,
                description=r.description,
                raw=r.raw,
            )
        )
    return out
