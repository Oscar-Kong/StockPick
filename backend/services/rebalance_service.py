"""Rebalance trade preview — separate from weight optimization."""
from __future__ import annotations

from typing import Any

from data.price_service import PriceService

WEIGHT_SUM_TOLERANCE = 1e-6


def _normalize_symbols(symbols: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for s in symbols:
        sym = (s or "").strip().upper()
        if not sym or sym in seen:
            continue
        seen.add(sym)
        out.append(sym)
    return out


def _fetch_prices(symbols: list[str]) -> dict[str, float]:
    ps = PriceService()
    prices: dict[str, float] = {}
    for sym in symbols:
        hist = ps.get_history(sym, period="5d")
        if hist.empty:
            continue
        prices[sym] = float(hist["close"].iloc[-1])
    return prices


def compute_rebalance_preview(
    *,
    holdings: list[dict[str, Any]],
    target_weights: dict[str, float],
    cash: float,
    cash_reserve: float = 0.05,
    min_trade_amount: float = 0.0,
    fractional_shares: bool = True,
    fee_bps: float = 0.0,
    slippage_bps: float = 0.0,
    max_turnover: float | None = None,
) -> dict[str, Any]:
    """
    Convert target weights into dollar/share trade preview.

    holdings: [{symbol, shares, avg_cost?, price?}]
    target_weights: symbol -> weight as fraction of invested capital (sum ≈ 1 - cash_reserve)
    """
    if cash < 0:
        raise ValueError("Cash cannot be negative")
    if not (0 <= cash_reserve < 1):
        raise ValueError("cash_reserve must be between 0 and 1")
    if fee_bps < 0 or slippage_bps < 0:
        raise ValueError("fee_bps and slippage_bps cannot be negative")

    normalized_targets = {k.upper(): max(0.0, float(v)) for k, v in target_weights.items()}
    symbols = _normalize_symbols([h.get("symbol", "") for h in holdings] + list(normalized_targets.keys()))
    if not symbols:
        raise ValueError("Provide at least one symbol")

    prices = _fetch_prices(symbols)
    for h in holdings:
        sym = str(h.get("symbol", "")).upper()
        if sym and h.get("price") is not None:
            prices[sym] = float(h["price"])

    missing = [s for s in symbols if s not in prices]
    if missing:
        raise ValueError(f"Missing price history for: {', '.join(missing)}")

    current_shares = {str(h.get("symbol", "")).upper(): float(h.get("shares") or 0) for h in holdings}
    invested_value = sum(current_shares.get(s, 0) * prices[s] for s in symbols if s in prices)
    total_value = invested_value + cash
    if total_value <= 0:
        raise ValueError("Portfolio has no value to rebalance")

    target_invested = total_value * (1.0 - cash_reserve)
    target_sum = sum(normalized_targets.values())
    if target_sum <= 0:
        raise ValueError("Target weights must sum to a positive value")
    scale = target_invested / target_sum
    scaled_targets = {s: w * scale for s, w in normalized_targets.items()}

    all_syms = sorted(set(symbols) | set(scaled_targets.keys()))
    trades: list[dict[str, Any]] = []
    turnover_dollars = 0.0
    constraint_violations: list[str] = []
    warnings: list[str] = []

    for sym in all_syms:
        price = prices.get(sym)
        if price is None or price <= 0:
            continue
        cur_shares = current_shares.get(sym, 0.0)
        cur_value = cur_shares * price
        cur_weight = cur_value / total_value if total_value > 0 else 0.0
        tgt_value = scaled_targets.get(sym, 0.0)
        tgt_weight = tgt_value / total_value if total_value > 0 else 0.0
        delta_value = tgt_value - cur_value

        if abs(delta_value) < min_trade_amount:
            share_delta = 0.0
            action = "hold"
            delta_value = 0.0
        else:
            share_delta = delta_value / price
            if not fractional_shares:
                share_delta = float(int(round(share_delta)))
                delta_value = share_delta * price
            if share_delta > WEIGHT_SUM_TOLERANCE:
                action = "buy"
            elif share_delta < -WEIGHT_SUM_TOLERANCE:
                action = "sell"
            else:
                action = "hold"
                share_delta = 0.0
                delta_value = 0.0

        fee = abs(delta_value) * fee_bps / 10_000.0
        slip = abs(delta_value) * slippage_bps / 10_000.0
        turnover_dollars += abs(delta_value)

        trades.append(
            {
                "symbol": sym,
                "current_shares": round(cur_shares, 4),
                "current_price": round(price, 4),
                "current_value": round(cur_value, 2),
                "current_weight": round(cur_weight, 4),
                "target_weight": round(tgt_weight, 4),
                "weight_difference": round(tgt_weight - cur_weight, 4),
                "target_value": round(tgt_value, 2),
                "dollar_trade": round(delta_value, 2),
                "share_trade": round(share_delta, 4),
                "action": action,
                "estimated_fee": round(fee, 2),
                "estimated_slippage": round(slip, 2),
                "post_trade_weight": round(tgt_weight, 4),
            }
        )

    turnover_pct = turnover_dollars / total_value if total_value > 0 else 0.0
    if max_turnover is not None and turnover_pct > max_turnover + WEIGHT_SUM_TOLERANCE:
        constraint_violations.append(
            f"Estimated turnover {turnover_pct:.1%} exceeds maximum {max_turnover:.1%}"
        )

    total_fees = sum(t["estimated_fee"] for t in trades)
    total_slippage = sum(t["estimated_slippage"] for t in trades)
    buy_total = sum(t["dollar_trade"] for t in trades if t["action"] == "buy")
    sell_total = sum(abs(t["dollar_trade"]) for t in trades if t["action"] == "sell")
    cash_after = cash - buy_total + sell_total - total_fees - total_slippage
    trade_count = sum(1 for t in trades if t["action"] in ("buy", "sell"))

    return {
        "total_value": round(total_value, 2),
        "cash_before": round(cash, 2),
        "cash_after": round(max(0.0, cash_after), 2),
        "cash_reserve": cash_reserve,
        "turnover_pct": round(turnover_pct, 4),
        "estimated_fees": round(total_fees, 2),
        "estimated_slippage": round(total_slippage, 2),
        "trade_count": trade_count,
        "trades": trades,
        "constraint_violations": constraint_violations,
        "warnings": warnings,
        "model_version": "rebalance-v1",
    }
