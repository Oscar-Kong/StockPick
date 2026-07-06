"""Canonical portfolio summary from the same ledger used by Home."""
from __future__ import annotations

from typing import Any

from datetime import datetime, timezone

from data.portfolio_store import get_latest_decision, get_latest_portfolio_snapshot
from data.price_service import PriceService
from services.data_freshness_service import assess_all_freshness, assess_freshness
from services.home_dashboard_service import build_daily_dashboard
from services.portfolio_snapshot_service import get_current_portfolio
from utils.datetime_util import utc_iso_z

WEIGHT_SUM_TOLERANCE = 1e-6


def _largest_sector(holdings: list[dict], decision_by_sym: dict[str, Any]) -> str | None:
    sectors: dict[str, float] = {}
    for h in holdings:
        sym = h.get("symbol", "")
        item = decision_by_sym.get(sym)
        weight = float(item.current_weight if item else 0)
        sector = (getattr(item, "sector", None) if item else None) or "Unclassified"
        sectors[sector] = sectors.get(sector, 0) + weight
    if not sectors:
        return None
    return max(sectors.items(), key=lambda kv: kv[1])[0]


def _portfolio_beta(holdings: list[dict], decision_by_sym: dict[str, Any]) -> float | None:
    weights: list[float] = []
    betas: list[float] = []
    for h in holdings:
        sym = h.get("symbol", "")
        item = decision_by_sym.get(sym)
        if not item:
            continue
        beta = getattr(item, "beta", None)
        w = float(item.current_weight or 0)
        if beta is not None and w > 0:
            weights.append(w)
            betas.append(float(beta))
    if not weights or sum(weights) <= 0:
        return None
    total_w = sum(weights)
    return round(sum(w * b for w, b in zip(weights, betas)) / total_w, 3)


def _position_rows(
    holdings: list[dict],
    decision_by_sym: dict[str, Any],
    total_value: float,
) -> list[dict[str, Any]]:
    ps = PriceService()
    rows: list[dict[str, Any]] = []
    for h in holdings:
        sym = str(h.get("symbol", "")).upper()
        shares = float(h.get("shares") or 0)
        avg_cost = float(h.get("avg_cost") or 0)
        item = decision_by_sym.get(sym)
        price = float(item.price) if item and item.price_available else None
        if price is None:
            latest = ps.get_latest_price(sym)
            if latest is not None:
                price = latest
        market_value = shares * price if price is not None else None
        if market_value is None and item:
            market_value = float(item.market_value or 0) or None
        weight = float(item.current_weight) if item else (
            (market_value / total_value) if market_value and total_value > 0 else None
        )
        pl_pct = float(item.pl_pct) if item and item.pl_pct is not None else (
            ((price - avg_cost) / avg_cost * 100) if price and avg_cost > 0 else None
        )
        daily_change_pct = None
        if price is not None:
            hist = ps.get_history(sym, period="5d")
            if len(hist) >= 2:
                prev = float(hist["close"].iloc[-2])
                if prev > 0:
                    daily_change_pct = round((price - prev) / prev * 100, 2)
        rows.append(
            {
                "symbol": sym,
                "company_name": None,
                "shares": round(shares, 4),
                "price": round(price, 4) if price is not None else None,
                "market_value": round(market_value, 2) if market_value is not None else None,
                "avg_cost": round(avg_cost, 4) if avg_cost else None,
                "unrealized_pl_pct": round(pl_pct, 2) if pl_pct is not None else None,
                "weight": round(weight, 4) if weight is not None else None,
                "daily_change_pct": daily_change_pct,
                "bucket": h.get("bucket"),
                "price_available": price is not None,
            }
        )
    rows.sort(key=lambda r: r.get("market_value") or 0, reverse=True)
    return rows


def build_portfolio_summary(*, include_freshness: bool = True) -> dict[str, Any]:
    """Single canonical summary for Portfolio Overview and Home-adjacent views."""
    dashboard = build_daily_dashboard(include_freshness=include_freshness)
    portfolio = get_current_portfolio()
    snap = get_latest_portfolio_snapshot()
    latest = get_latest_decision()

    decision = dashboard.decision
    decision_by_sym = {i.symbol: i for i in (decision.items if decision else [])}
    holdings = dashboard.holdings or []
    total_value = float(dashboard.portfolio_value or 0)
    cash = float(dashboard.cash or 0)
    invested = float(dashboard.invested_value or 0)
    positions = _position_rows(holdings, decision_by_sym, total_value)

    largest_position = positions[0]["symbol"] if positions else None
    largest_weight = positions[0].get("weight") if positions else None

    price_as_of = None
    if snap and snap.get("created_at"):
        price_as_of = str(snap["created_at"])[:10]

    freshness = dashboard.freshness
    price_status = assess_freshness("latest_prices") if include_freshness else None

    warnings: list[str] = list(dashboard.portfolio_warnings or [])
    stale = bool(dashboard.decision_stale_warning) or (
        price_status.is_stale if price_status else False
    )

    account = portfolio.get("account") or {}
    as_of = account.get("last_sync_at") or (
        latest.get("created_at") if latest else None
    )
    if as_of is None:
        as_of = utc_iso_z(datetime.now(timezone.utc))

    return {
        "as_of": as_of,
        "price_as_of": price_as_of,
        "total_value": round(total_value, 2),
        "invested_value": round(invested, 2),
        "cash": round(cash, 2),
        "reserved_cash": round(float(dashboard.reserved_cash or 0), 2),
        "cash_weight": round(cash / total_value, 4) if total_value > 0 else 0.0,
        "today_change_pct": None,
        "total_unrealized_pl_pct": None,
        "active_holdings_count": len(holdings),
        "largest_position": largest_position,
        "largest_position_weight": largest_weight,
        "largest_sector": _largest_sector(holdings, decision_by_sym),
        "portfolio_beta": _portfolio_beta(holdings, decision_by_sym),
        "estimated_annual_volatility": None,
        "holdings_updated_at": as_of,
        "last_price_update_at": price_status.last_updated_at if price_status else price_as_of,
        "risk_model_through": price_as_of,
        "positions": positions,
        "source": "portfolio_ledger",
        "data_source": dashboard.data_source,
        "data_source_label": dashboard.data_source_label,
        "is_demo_data": bool(dashboard.is_demo_data),
        "stale": stale,
        "warnings": warnings,
        "freshness": freshness.model_dump() if freshness else None,
        "disclaimer": dashboard.disclaimer,
    }
