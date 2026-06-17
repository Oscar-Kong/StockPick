"""Detect and collapse duplicate Robinhood ledger rows (e.g. re-imports with missing dates)."""
from __future__ import annotations

from integrations.robinhood.csv_importer import _effective_fill_price
from integrations.robinhood.models import ParsedCsvRow, normalize_row_type


def _row_completeness(row: ParsedCsvRow) -> int:
    score = 0
    if row.activity_date:
        score += 4
    if row.process_date:
        score += 1
    if row.executed_at:
        score += 2
    if row.amount and abs(row.amount) > 1e-9:
        score += 4
    if row.description:
        score += 1
    return score


def apply_effective_fill_price(row: ParsedCsvRow) -> ParsedCsvRow:
    """Use signed Amount / Quantity when Robinhood's Price column is wrong."""
    if row.row_type in ("buy", "sell") and row.quantity and row.amount:
        row.price = _effective_fill_price(
            price=row.price,
            quantity=float(row.quantity),
            amount=float(row.amount),
        )
    return row


def semantic_ledger_key(row: ParsedCsvRow) -> tuple:
    rt = normalize_row_type(row.row_type)
    if rt == "event":
        return (
            "event",
            (row.trans_code or "").upper(),
            round(float(row.amount or 0), 2),
        )
    qty = round(float(row.quantity or 0), 6)
    amount = round(float(row.amount or 0), 2)
    return (rt, (row.instrument or "").upper(), qty, amount)


def is_incomplete_ghost_row(row: ParsedCsvRow) -> bool:
    """Rows missing dates and amounts are usually duplicate CSV re-import artifacts."""
    if row.row_type not in ("buy", "sell"):
        return False
    if (row.activity_date or "").strip():
        return False
    return abs(float(row.amount or 0)) < 1e-9


def dedupe_parsed_rows(rows: list[ParsedCsvRow]) -> tuple[list[ParsedCsvRow], int]:
    """Keep the most complete row per semantic trade/cash key; preserve first-seen order."""
    filtered = [r for r in rows if not is_incomplete_ghost_row(r)]
    removed = len(rows) - len(filtered)
    best: dict[tuple, ParsedCsvRow] = {}
    order: list[tuple] = []
    for row in filtered:
        apply_effective_fill_price(row)
        key = semantic_ledger_key(row)
        existing = best.get(key)
        if existing is None:
            best[key] = row
            order.append(key)
        elif _row_completeness(row) > _row_completeness(existing):
            best[key] = row
    deduped = [best[k] for k in order]
    return deduped, removed + max(0, len(filtered) - len(deduped))
