"""Verify manual journal trades against CSV / portfolio ledger after import."""
from __future__ import annotations

from integrations.robinhood.models import ParsedCsvRow

QTY_TOLERANCE = 0.02
PRICE_TOLERANCE_PCT = 0.05


def is_manual_journal_ledger_row(*, trans_code: str | None, description: str | None, row_hash: str | None = None) -> bool:
    if (trans_code or "").upper() == "MANUAL":
        return True
    if "[journal #" in (description or ""):
        return True
    if row_hash and row_hash.startswith("journal-"):
        return False  # hashes are sha256; use trans_code/description
    return False


def _find_matching_buy(
    symbol: str,
    quantity: float,
    entry_price: float,
    rows: list[ParsedCsvRow],
) -> ParsedCsvRow | None:
    sym = symbol.upper()
    for row in rows:
        if row.row_type != "buy":
            continue
        if (row.instrument or "").upper() != sym:
            continue
        row_qty = float(row.quantity or 0)
        if abs(row_qty - quantity) > QTY_TOLERANCE:
            continue
        row_price = float(row.price or 0)
        if entry_price > 0 and row_price > 0:
            if abs(row_price - entry_price) / max(entry_price, 0.01) > PRICE_TOLERANCE_PCT:
                continue
        return row
    return None


def verify_journal_trades_against_ledger(
    account_id: int,
    *,
    csv_rows: list[ParsedCsvRow] | None = None,
    journal_ledger_hash_fn,
    ledger_has_hash_fn,
    list_journal_trades_fn,
    load_ledger_rows_fn,
) -> list[dict]:
    """
    After a CSV import, check each journal trade with quantity:
    - synced: manual row already in ledger
    - matched: CSV contains a matching buy (broker confirms the manual log)
    - missing: no ledger or CSV match
    """
    csv_buys = [r for r in (csv_rows or []) if r.row_type == "buy"]
    ledger_rows = load_ledger_rows_fn(account_id)
    ledger_buys = [r for r in ledger_rows if r.row_type == "buy"]

    results: list[dict] = []
    for trade in list_journal_trades_fn(limit=500):
        trade_id = int(trade["id"])
        symbol = (trade.get("symbol") or "").upper()
        qty = float(trade.get("quantity") or 0)
        entry = float(trade.get("entry_price") or 0)

        if qty <= 0:
            results.append(
                {
                    "trade_id": trade_id,
                    "symbol": symbol,
                    "status": "skipped",
                    "message": "No share quantity — journal only",
                }
            )
            continue

        buy_hash = journal_ledger_hash_fn(trade_id, "buy")
        if ledger_has_hash_fn(buy_hash):
            results.append(
                {
                    "trade_id": trade_id,
                    "symbol": symbol,
                    "status": "synced",
                    "message": "Manual entry already in portfolio ledger",
                }
            )
            continue

        match = _find_matching_buy(symbol, qty, entry, csv_buys)
        if match:
            results.append(
                {
                    "trade_id": trade_id,
                    "symbol": symbol,
                    "status": "matched_csv",
                    "message": f"CSV confirms buy {symbol} × {qty} @ {match.price}",
                }
            )
            continue

        match = _find_matching_buy(symbol, qty, entry, ledger_buys)
        if match and not is_manual_journal_ledger_row(
            trans_code=match.trans_code, description=match.description, row_hash=match.row_hash
        ):
            results.append(
                {
                    "trade_id": trade_id,
                    "symbol": symbol,
                    "status": "matched_ledger",
                    "message": f"Ledger buy {symbol} × {qty} matches journal",
                }
            )
            continue

        results.append(
            {
                "trade_id": trade_id,
                "symbol": symbol,
                "status": "missing",
                "message": f"No CSV or ledger buy found for {symbol} × {qty}",
            }
        )

    return results
