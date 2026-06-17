"""Rebuild open holdings, closed positions, and cash from parsed CSV rows.

Cost basis method: **weighted average cost**.
Position rows (buy/sell) update holdings. Event rows (deposits, dividends, etc.)
live in a separate event ledger and only affect cash.
"""
from __future__ import annotations

from datetime import datetime

from integrations.robinhood.models import (
    ClosedPosition,
    MiscEventRow,
    ParsedCsvRow,
    PortfolioRebuildResult,
    ReconstructedHolding,
    normalize_row_type,
)

MIN_OPEN_SHARES = 1e-4


def _cash_impact(row: ParsedCsvRow) -> float:
    """Signed cash flow from a ledger row."""
    rt = normalize_row_type(row.row_type)
    if rt == "event":
        return float(row.amount)
    if rt == "buy":
        if row.amount != 0:
            return float(row.amount)
        qty = float(row.quantity or 0)
        price = float(row.price or 0)
        return -(qty * price)
    if rt == "sell":
        if row.amount != 0:
            return float(row.amount)
        qty = float(row.quantity or 0)
        price = float(row.price or 0)
        return qty * price
    return 0.0


def _event_row(row: ParsedCsvRow) -> MiscEventRow:
    return MiscEventRow(
        activity_date=row.activity_date,
        trans_code=row.trans_code,
        description=(row.description or "")[:200],
        amount=round(float(row.amount), 2),
        instrument=row.instrument or "",
    )


def rebuild_portfolio(rows: list[ParsedCsvRow]) -> PortfolioRebuildResult:
    warnings: list[str] = []
    excluded: list[dict] = []
    unknown: list[str] = []
    cash_delta = 0.0
    event_ledger: list[MiscEventRow] = []

    lots: dict[str, dict] = {}
    closed: dict[str, ClosedPosition] = {}

    sorted_rows = sorted(
        rows,
        key=lambda r: (
            r.executed_at or datetime.min,
            r.activity_date,
            r.process_date,
        ),
    )

    for row in sorted_rows:
        row_type = normalize_row_type(row.row_type)

        if row_type == "excluded":
            excluded.append({"trans_code": row.trans_code, "description": row.description[:120]})
            if row.trans_code:
                unknown.append(row.trans_code)
            continue

        if row_type == "event":
            cash_delta += _cash_impact(row)
            event_ledger.append(_event_row(row))
            continue

        if row_type not in ("buy", "sell"):
            continue

        sym = row.instrument.upper()
        if not sym:
            excluded.append({"reason": "missing symbol", "row": row.trans_code})
            continue

        qty = abs(float(row.quantity or 0))
        if qty <= 0:
            continue

        price = float(row.price or 0)
        if sym not in lots:
            lots[sym] = {
                "shares": 0.0,
                "cost": 0.0,
                "bought": 0.0,
                "sold": 0.0,
                "realized": 0.0,
                "last": row.activity_date,
            }

        lot = lots[sym]
        lot["last"] = row.activity_date or lot["last"]

        if row_type == "buy":
            cost_add = qty * price
            lot["shares"] += qty
            lot["cost"] += cost_add
            lot["bought"] += qty
            cash_delta += _cash_impact(row)
        else:  # sell
            held = lot["shares"]
            if held <= MIN_OPEN_SHARES:
                warnings.append(f"Sell {sym} with no open shares — ignored")
                continue
            sell_qty = min(qty, held)
            avg = lot["cost"] / held if held else price
            proceeds = sell_qty * price
            cost_removed = avg * sell_qty
            lot["realized"] += proceeds - cost_removed
            lot["shares"] -= sell_qty
            lot["cost"] -= cost_removed
            lot["sold"] += sell_qty
            cash_delta += _cash_impact(row)

            if lot["shares"] <= MIN_OPEN_SHARES:
                closed[sym] = ClosedPosition(
                    symbol=sym,
                    total_bought=lot["bought"],
                    total_sold=lot["sold"],
                    realized_pl=round(lot["realized"], 2),
                    last_activity=lot["last"],
                )
                del lots[sym]

    open_holdings: list[ReconstructedHolding] = []
    for sym, lot in sorted(lots.items()):
        shares = round(lot["shares"], 8)
        if shares <= MIN_OPEN_SHARES:
            continue
        avg_cost = round(lot["cost"] / shares, 6) if shares else 0.0
        from integrations.robinhood.base import classify_holding_bucket

        open_holdings.append(
            ReconstructedHolding(
                symbol=sym,
                shares=shares,
                avg_cost=avg_cost,
                bucket=classify_holding_bucket(sym, avg_cost),
                total_bought=lot["bought"],
                total_sold=lot["sold"],
                realized_pl=round(lot["realized"], 2),
            )
        )

    return PortfolioRebuildResult(
        open_holdings=open_holdings,
        closed_positions=sorted(closed.values(), key=lambda c: c.symbol),
        cash_delta=round(cash_delta, 2),
        event_ledger=event_ledger,
        excluded_rows=excluded,
        unknown_trans_codes=sorted(set(unknown)),
        warnings=warnings,
    )


def validation_report(rows: list[ParsedCsvRow], rebuild: PortfolioRebuildResult) -> list[dict]:
    """Per-symbol validation breakdown for dev endpoint."""
    by_sym: dict[str, dict] = {}

    for row in rows:
        if normalize_row_type(row.row_type) not in ("buy", "sell"):
            continue
        sym = row.instrument.upper()
        if not sym:
            continue
        if sym not in by_sym:
            by_sym[sym] = {
                "symbol": sym,
                "total_bought_shares": 0.0,
                "total_sold_shares": 0.0,
                "open_shares": 0.0,
                "avg_cost": None,
                "realized_pl": 0.0,
                "cash_impact": 0.0,
            }
        qty = abs(float(row.quantity or 0))
        if normalize_row_type(row.row_type) == "buy":
            by_sym[sym]["total_bought_shares"] += qty
        else:
            by_sym[sym]["total_sold_shares"] += qty
        by_sym[sym]["cash_impact"] += _cash_impact(row)

    for h in rebuild.open_holdings:
        if h.symbol in by_sym:
            by_sym[h.symbol]["open_shares"] = h.shares
            by_sym[h.symbol]["avg_cost"] = h.avg_cost
            by_sym[h.symbol]["realized_pl"] = h.realized_pl

    for c in rebuild.closed_positions:
        entry = by_sym.setdefault(
            c.symbol,
            {
                "symbol": c.symbol,
                "total_bought_shares": c.total_bought,
                "total_sold_shares": c.total_sold,
                "open_shares": 0.0,
                "avg_cost": None,
                "realized_pl": c.realized_pl,
                "cash_impact": 0.0,
            },
        )
        entry["open_shares"] = 0.0
        entry["realized_pl"] = c.realized_pl

    return list(by_sym.values())
