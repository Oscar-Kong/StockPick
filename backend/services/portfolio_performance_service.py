"""Portfolio P/L metrics and mark-to-market equity curves from live holdings."""
from __future__ import annotations

import copy
import hashlib
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

import pandas as pd

from config import PORTFOLIO_PERFORMANCE_CACHE_TTL
from data.cache import Cache
from data.portfolio_store import DEFAULT_ACCOUNT_ID, load_all_ledger_rows
from data.price_service import PriceService
from integrations.robinhood.mcp_client import RobinhoodMcpClient
from integrations.robinhood.mcp_pnl import RealizedPnlSummary
from integrations.robinhood.models import ParsedCsvRow, normalize_row_type
from integrations.robinhood.portfolio_rebuilder import MIN_OPEN_SHARES, _cash_impact
from services.portfolio_summary_service import build_portfolio_summary

logger = logging.getLogger(__name__)

RANGE_SPECS: dict[str, tuple[str, int]] = {
    "1d": ("5d", 5),
    "1w": ("1mo", 7),
    "1m": ("1mo", 22),
    "6m": ("6mo", 130),
    "1y": ("1y", 252),
}

# One 1y history fetch reused for every chart range (avoids 5× ledger replay + price I/O).
CHART_HISTORY_PERIOD = "1y"
CHART_PRICE_WORKERS = 4
CHART_SYMBOL_FETCH_TIMEOUT_S = 12.0


@dataclass(frozen=True)
class _LedgerReplay:
    snapshots: dict[date, tuple[float, dict[str, dict[str, float]]]]
    snapshot_dates: tuple[date, ...]
    deposit_adjustment: float
    start_date: date
    symbols: frozenset[str]


def _ytd_floor() -> str:
    return f"{date.today().year}-01-01"


def _ytd_floor_date() -> date:
    return date.fromisoformat(_ytd_floor())


def _parse_activity_date(raw: str | None) -> date | None:
    if not raw:
        return None
    text = str(raw).strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(text[:10] if fmt == "%Y-%m-%d" else text, fmt).date()
        except ValueError:
            continue
    return None


def _parse_row_date(row: ParsedCsvRow) -> date | None:
    if row.executed_at is not None:
        return row.executed_at.date()
    return _parse_activity_date(row.activity_date) or _parse_activity_date(row.process_date)


def _filter_curve_ytd(curve: list[dict[str, Any]]) -> list[dict[str, Any]]:
    floor = _ytd_floor()
    filtered = [p for p in curve if str(p.get("date") or "")[:10] >= floor]
    if not filtered and curve:
        return [curve[-1]]
    return filtered


def _slice_curve(curve: list[dict[str, Any]], max_points: int) -> list[dict[str, Any]]:
    if max_points > 0 and len(curve) > max_points:
        return curve[-max_points:]
    return curve


def _performance_cache_key(summary: dict[str, Any]) -> str:
    parts = [
        str(date.today()),
        str(round(float(summary.get("total_value") or 0), 2)),
        str(round(float(summary.get("cash") or 0), 2)),
    ]
    for pos in sorted(summary.get("positions") or [], key=lambda p: str(p.get("symbol") or "")):
        parts.append(f"{pos.get('symbol')}:{round(float(pos.get('shares') or 0), 4)}")
    digest = hashlib.sha256("|".join(parts).encode()).hexdigest()[:20]
    return f"portfolio:performance:v2:{digest}"


def _closed_realized_ytd(closed: list[dict[str, Any]]) -> float:
    floor = _ytd_floor_date()
    total = 0.0
    for c in closed:
        activity = _parse_activity_date(c.get("last_activity"))
        if activity is None or activity < floor:
            continue
        total += float(c.get("realized_pl") or 0)
    return total


def _resolve_realized_ytd(closed: list[dict[str, Any]]) -> RealizedPnlSummary:
    mcp = RobinhoodMcpClient().fetch_ytd_realized_pnl_sync()
    if mcp is not None:
        return mcp
    ledger_total = round(_closed_realized_ytd(closed), 2)
    return RealizedPnlSummary(
        total=ledger_total,
        equity=ledger_total,
        events=0.0,
        trade_count=0,
        source="ledger",
    )


def _unrealized_from_positions(positions: list[dict[str, Any]]) -> tuple[float, float]:
    unrealized = 0.0
    cost_basis = 0.0
    for p in positions:
        shares = float(p.get("shares") or 0)
        avg_cost = float(p.get("avg_cost") or 0)
        if shares <= 0:
            continue
        cost = shares * avg_cost
        cost_basis += cost
        market_value = p.get("market_value")
        price = p.get("price")
        if market_value is not None:
            unrealized += float(market_value) - cost
        elif price is not None:
            unrealized += shares * float(price) - cost
    return round(unrealized, 2), round(cost_basis, 2)


def _curve_period_change(curve: list[dict[str, Any]]) -> float | None:
    if len(curve) < 2:
        return None
    start = float(curve[0]["value"])
    end = float(curve[-1]["value"])
    if start <= 0:
        return None
    return round((end / start - 1) * 100, 2)


def _apply_trade_row(lots: dict[str, dict[str, float]], cash: float, row: ParsedCsvRow) -> float:
    row_type = normalize_row_type(row.row_type)
    if row_type == "event":
        return cash + _cash_impact(row)
    if row_type not in ("buy", "sell"):
        return cash

    sym = (row.instrument or "").upper()
    if not sym:
        return cash

    qty = abs(float(row.quantity or 0))
    if qty <= 0:
        return cash

    price = float(row.price or 0)
    lot = lots.setdefault(sym, {"shares": 0.0, "cost": 0.0})
    cash += _cash_impact(row)

    if row_type == "buy":
        lot["shares"] += qty
        lot["cost"] += qty * price
    else:
        held = lot["shares"]
        if held <= MIN_OPEN_SHARES:
            return cash
        sell_qty = min(qty, held)
        avg = lot["cost"] / held if held else price
        lot["shares"] -= sell_qty
        lot["cost"] -= avg * sell_qty
        if lot["shares"] <= MIN_OPEN_SHARES:
            del lots[sym]
    return cash


def _prepare_ledger_replay(*, live_cash: float, live_reserved: float) -> _LedgerReplay | None:
    floor = _ytd_floor_date()
    ledger_rows = load_all_ledger_rows(DEFAULT_ACCOUNT_ID)
    ytd_rows = [r for r in ledger_rows if _parse_row_date(r) and _parse_row_date(r) >= floor]
    if not ytd_rows:
        return None

    sorted_rows = sorted(ytd_rows, key=lambda r: (_parse_row_date(r), r.activity_date or "", r.process_date or ""))

    lots: dict[str, dict[str, float]] = {}
    cash = 0.0
    snapshots: dict[date, tuple[float, dict[str, dict[str, float]]]] = {}
    symbols: set[str] = set()

    for row in sorted_rows:
        row_date = _parse_row_date(row)
        if row_date is None:
            continue
        cash = _apply_trade_row(lots, cash, row)
        snapshots[row_date] = (cash, copy.deepcopy(lots))
        symbols.update(lots.keys())

    if not snapshots:
        return None

    return _LedgerReplay(
        snapshots=snapshots,
        snapshot_dates=tuple(sorted(snapshots.keys())),
        deposit_adjustment=float(live_cash) + float(live_reserved) - cash,
        start_date=min(snapshots.keys()),
        symbols=frozenset(symbols),
    )


def _series_from_history(df: pd.DataFrame | None) -> pd.Series | None:
    if df is None or df.empty:
        return None
    local = df.copy()
    local["date"] = pd.to_datetime(local["date"]).dt.date
    local = local.sort_values("date")
    return local.set_index("date")["close"]


def _fetch_close_history(symbols: frozenset[str], ps: PriceService, *, period: str) -> dict[str, pd.Series]:
    if not symbols:
        return {}

    def _fetch(sym: str) -> tuple[str, pd.Series | None]:
        try:
            return sym, _series_from_history(ps.get_history(sym, period=period))
        except Exception:
            logger.debug("price history failed for %s", sym, exc_info=True)
            return sym, None

    out: dict[str, pd.Series] = {}
    workers = min(CHART_PRICE_WORKERS, max(1, len(symbols)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_fetch, sym): sym for sym in symbols}
        try:
            for fut in as_completed(futures, timeout=CHART_SYMBOL_FETCH_TIMEOUT_S * len(symbols)):
                sym, series = fut.result()
                if series is not None and not series.empty:
                    out[sym] = series
        except TimeoutError:
            logger.warning("portfolio chart price fetch timed out (%d symbols)", len(symbols))
            for fut in futures:
                if fut.done() and not fut.cancelled():
                    sym, series = fut.result()
                    if series is not None and not series.empty:
                        out[sym] = series
    return out


def _build_curve_from_replay(
    replay: _LedgerReplay,
    close_by_sym: dict[str, pd.Series],
    *,
    target_total: float,
) -> list[dict[str, Any]]:
    if not close_by_sym:
        return []

    all_dates = sorted(set().union(*[s.index for s in close_by_sym.values()]))
    all_dates = [d for d in all_dates if d >= replay.start_date]
    if not all_dates:
        return []

    out: list[dict[str, Any]] = []

    def _state_on(day: date) -> tuple[float, dict[str, dict[str, float]]]:
        applicable = [d for d in replay.snapshot_dates if d <= day]
        if not applicable:
            return 0.0, {}
        return replay.snapshots[applicable[-1]]

    for day in all_dates:
        day_cash, day_lots = _state_on(day)
        invested = 0.0
        for sym, lot in day_lots.items():
            series = close_by_sym.get(sym)
            if series is None or day not in series.index:
                continue
            px = float(series.loc[day])
            if pd.isna(px):
                continue
            invested += float(lot["shares"]) * px
        value = round(invested + day_cash + replay.deposit_adjustment, 2)
        out.append({"date": day.isoformat(), "value": value})

    if out:
        out[-1]["value"] = round(target_total, 2)
    return _filter_curve_ytd(out)


def _build_equity_curve_fallback(
    holdings: list[dict[str, Any]],
    cash: float,
    reserved_cash: float,
    *,
    fetch_period: str,
    max_points: int,
) -> list[dict[str, Any]]:
    if not holdings:
        total = round(cash + reserved_cash, 2)
        return [{"date": date.today().isoformat(), "value": total}]

    ps = PriceService()
    symbols = frozenset(
        str(h.get("symbol") or "").upper()
        for h in holdings
        if str(h.get("symbol") or "").strip() and float(h.get("shares") or 0) > 0
    )
    close_by_sym = _fetch_close_history(symbols, ps, period=fetch_period)
    shares_by_sym = {
        str(h.get("symbol") or "").upper(): float(h.get("shares") or 0)
        for h in holdings
    }

    series_by_sym: dict[str, pd.Series] = {}
    for sym, close in close_by_sym.items():
        shares = shares_by_sym.get(sym, 0.0)
        if shares > 0:
            series_by_sym[sym] = close * shares

    if not series_by_sym:
        total = round(cash + reserved_cash, 2)
        return [{"date": date.today().isoformat(), "value": total}]

    combined = pd.concat(series_by_sym.values(), axis=1).sort_index().ffill()
    invested = combined.sum(axis=1)
    static_cash = float(cash) + float(reserved_cash)
    total = invested + static_cash

    out: list[dict[str, Any]] = []
    for idx, val in total.items():
        if pd.isna(val):
            continue
        out.append({"date": idx.strftime("%Y-%m-%d"), "value": round(float(val), 2)})

    return _slice_curve(_filter_curve_ytd(out), max_points)


def _build_all_curves(
    *,
    holdings: list[dict[str, Any]],
    cash: float,
    reserved: float,
    target_total: float,
) -> dict[str, list[dict[str, Any]]]:
    replay = _prepare_ledger_replay(live_cash=cash, live_reserved=reserved)
    full_curve: list[dict[str, Any]] = []

    if replay is not None:
        ps = PriceService()
        close_by_sym = _fetch_close_history(replay.symbols, ps, period=CHART_HISTORY_PERIOD)
        full_curve = _build_curve_from_replay(replay, close_by_sym, target_total=target_total)

    curves: dict[str, list[dict[str, Any]]] = {}
    for key, (_fetch_period, max_points) in RANGE_SPECS.items():
        if full_curve:
            curves[key] = _slice_curve(full_curve, max_points)
        else:
            curves[key] = _build_equity_curve_fallback(
                holdings,
                cash,
                reserved,
                fetch_period=CHART_HISTORY_PERIOD,
                max_points=max_points,
            )
    return curves


def _compute_metrics(
    summary: dict[str, Any],
    closed: list[dict[str, Any]],
    *,
    realized_summary: RealizedPnlSummary | None = None,
) -> dict[str, float | None | str]:
    positions = summary.get("positions") or []
    total_value = float(summary.get("total_value") or 0)

    today_pl = 0.0
    for p in positions:
        shares = float(p.get("shares") or 0)
        price = p.get("price")
        dcp = p.get("daily_change_pct")
        if price is not None and dcp is not None and shares > 0:
            prev = float(price) / (1 + float(dcp) / 100)
            today_pl += shares * (float(price) - prev)

    realized = realized_summary or _resolve_realized_ytd(closed)
    unrealized, cost_basis = _unrealized_from_positions(positions)

    today_base = total_value - today_pl
    return {
        "today_pl": round(today_pl, 2),
        "today_pl_pct": round(today_pl / today_base * 100, 2) if today_base > 0 else None,
        "unrealized_pl": unrealized,
        "unrealized_pl_pct": round(unrealized / cost_basis * 100, 2) if cost_basis > 0 else None,
        "realized_pl": realized.total,
        "realized_pl_equity": realized.equity,
        "realized_pl_events": realized.events,
        "realized_pl_source": realized.source,
    }


def build_portfolio_performance(*, closed_positions: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    summary = build_portfolio_summary(include_freshness=False)
    cache_key = _performance_cache_key(summary)
    cached = Cache().get(cache_key)
    if isinstance(cached, dict) and cached.get("total_value") is not None:
        return cached

    closed = closed_positions if closed_positions is not None else []

    holdings = [
        {"symbol": h["symbol"], "shares": h["shares"], "avg_cost": h.get("avg_cost", 0)}
        for h in (summary.get("positions") or [])
    ]
    cash = float(summary.get("cash") or 0)
    reserved = float(summary.get("reserved_cash") or 0)
    total_value = round(float(summary.get("total_value") or 0), 2)

    realized_summary: RealizedPnlSummary | None = None
    curves: dict[str, list[dict[str, Any]]] = {}

    with ThreadPoolExecutor(max_workers=2) as pool:
        mcp_future = pool.submit(_resolve_realized_ytd, closed)
        curves_future = pool.submit(
            _build_all_curves,
            holdings=holdings,
            cash=cash,
            reserved=reserved,
            target_total=total_value,
        )
        try:
            realized_summary = mcp_future.result()
        except Exception:
            logger.exception("realized P/L fetch failed")
        try:
            curves = curves_future.result()
        except Exception:
            logger.exception("portfolio curve build failed")
            curves = {}

    if not curves:
        curves = _build_all_curves(
            holdings=holdings,
            cash=cash,
            reserved=reserved,
            target_total=total_value,
        )

    metrics = _compute_metrics(summary, closed, realized_summary=realized_summary)
    period_change_pct = {key: _curve_period_change(curve) for key, curve in curves.items()}

    year = date.today().year
    source = metrics.get("realized_pl_source", "ledger")
    disclaimer = (
        f"{year} YTD: unrealized P/L is open-position cost basis; realized P/L from "
        f"{'Robinhood MCP trade history (stocks + event/prediction contracts)' if source == 'robinhood_mcp' else 'closed equity lots in the ledger'}. "
        "Chart replays equity trades; MCP deposits are estimated from buying power."
    )
    result = {
        "total_value": total_value,
        "invested_value": round(float(summary.get("invested_value") or 0), 2),
        "cash": round(cash, 2),
        "as_of": summary.get("as_of"),
        **metrics,
        "curves": curves,
        "period_change_pct": period_change_pct,
        "disclaimer": disclaimer,
    }
    if PORTFOLIO_PERFORMANCE_CACHE_TTL > 0:
        Cache().set(cache_key, result, PORTFOLIO_PERFORMANCE_CACHE_TTL)
    return result
