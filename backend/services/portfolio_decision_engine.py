"""Portfolio buy/keep/sell decision engine with explainability."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from config import SLEEVE_MAX_WEIGHT

FinalDecision = Literal["buy", "keep", "sell", "review"]


@dataclass
class DecisionInput:
    symbol: str
    sleeve: str
    shares: float
    avg_cost: float
    latest_price: float | None
    alpha_score: float
    momentum_score: float
    liquidity_score: float
    risk_score: float
    data_quality_score: float | None
    current_weight: float
    target_weight: float
    max_allowed_weight: float
    price_stale: bool = False


@dataclass
class DecisionOutput:
    final_decision: FinalDecision
    buy_pct: float
    keep_pct: float
    sell_pct: float
    suggested_action: str
    suggested_dollar_action: float
    reasons: list[str] = field(default_factory=list)
    risk_flags: list[str] = field(default_factory=list)
    # debug
    alpha_score: float = 0.0
    momentum_score: float = 0.0
    liquidity_score: float = 0.0
    risk_score: float = 0.0
    data_quality_score: float | None = None
    current_weight: float = 0.0
    target_weight: float = 0.0
    max_allowed_weight: float = 0.0
    overweight_penalty: float = 0.0
    missing_data_penalty: float = 0.0
    stop_loss_trigger: bool = False
    final_buy_raw: float = 0.0
    final_keep_raw: float = 0.0
    final_sell_raw: float = 0.0
    price_available: bool = True


def _normalize(b: float, k: float, s: float) -> tuple[float, float, float]:
    total = b + k + s
    if total <= 0:
        return 33.33, 33.34, 33.33
    buy_pct = round(100 * b / total, 2)
    keep_pct = round(100 * k / total, 2)
    sell_pct = round(100 * s / total, 2)
    drift = 100.0 - (buy_pct + keep_pct + sell_pct)
    if abs(drift) > 0.001:
        keep_pct = round(keep_pct + drift, 2)
    return buy_pct, keep_pct, sell_pct


def _suggested_action(decision: FinalDecision, delta_usd: float, overweight: bool) -> str:
    if decision == "review":
        return "Review — missing or low-quality data"
    if decision == "buy":
        return f"Consider adding ~${abs(delta_usd):,.0f}" if delta_usd > 0 else "Hold size; score supports add when cash allows"
    if decision == "sell":
        if overweight:
            return "Trim or exit — position oversized / risk elevated"
        return "Consider reducing or exiting"
    if overweight:
        return "Hold but do not add — near or above max weight"
    return "Hold — mixed signals; no action required"


def compute_holding_decision(inp: DecisionInput, *, total_portfolio_value: float) -> DecisionOutput:
    reasons: list[str] = []
    flags: list[str] = []

    dq = inp.data_quality_score
    if dq is not None and dq < 45:
        flags.append("low_data_quality")

    missing_penalty = 0.0
    price_ok = inp.latest_price is not None and inp.latest_price > 0

    if not price_ok:
        missing_penalty = 100.0
        flags.append("missing_price")
        b, k, s = 0.0, 0.0, 100.0
        buy_pct, keep_pct, sell_pct = _normalize(b, k, s)
        return DecisionOutput(
            final_decision="review",
            buy_pct=buy_pct,
            keep_pct=keep_pct,
            sell_pct=sell_pct,
            suggested_action="Review — latest price unavailable",
            suggested_dollar_action=0.0,
            reasons=["Latest price missing — cannot size or score confidently"],
            risk_flags=flags,
            alpha_score=inp.alpha_score,
            momentum_score=inp.momentum_score,
            liquidity_score=inp.liquidity_score,
            risk_score=inp.risk_score,
            data_quality_score=dq,
            current_weight=inp.current_weight,
            target_weight=inp.target_weight,
            max_allowed_weight=inp.max_allowed_weight,
            missing_data_penalty=missing_penalty,
            final_buy_raw=b,
            final_keep_raw=k,
            final_sell_raw=s,
            price_available=False,
        )

    price = float(inp.latest_price)
    pl_pct = ((price - inp.avg_cost) / inp.avg_cost * 100) if inp.avg_cost > 0 else 0.0
    stop_loss = inp.sleeve == "penny" and pl_pct <= -25.0
    if stop_loss:
        flags.append("stop_loss_trigger")
        reasons.append(f"Drawdown {pl_pct:.1f}% triggers penny stop review")

    overweight = inp.current_weight > inp.max_allowed_weight
    ow_penalty = 0.0
    if overweight:
        ow_penalty = min(80.0, (inp.current_weight / max(inp.max_allowed_weight, 0.001) - 1) * 100)
        flags.append("overweight")
        reasons.append(f"Weight {inp.current_weight*100:.1f}% exceeds max {inp.max_allowed_weight*100:.1f}%")

    # Raw directional scores (0–100 scale inputs)
    alpha = max(0.0, min(100.0, inp.alpha_score))
    mom = max(0.0, min(100.0, inp.momentum_score))
    liq = max(0.0, min(100.0, inp.liquidity_score))
    risk = max(0.0, min(100.0, inp.risk_score))

    buy_raw = max(0.0, (alpha - 50) * 0.4 + (mom - 50) * 0.35 + (liq - 50) * 0.15)
    sell_raw = max(0.0, (risk - 50) * 0.45 + (50 - mom) * 0.25 + ow_penalty * 0.5)
    keep_raw = max(15.0, 55.0 - abs(alpha - 55) * 0.3 - abs(mom - 50) * 0.2)

    if stop_loss:
        sell_raw += 40.0

    block_buy = False
    if inp.price_stale:
        flags.append("stale_price")
        buy_raw = 0.0
        block_buy = True
        reasons.append("Latest price is stale — refresh before acting; buy suppressed")
        if inp.sleeve == "penny":
            reasons.append("Penny add blocked — stale price data")

    # Penny conservative gates — do NOT recommend buy
    if inp.sleeve == "penny":
        if overweight:
            block_buy = True
            reasons.append("Penny add blocked — already above max position size")
        if inp.current_weight >= inp.target_weight * 1.05:
            block_buy = True
            reasons.append("Penny add blocked — at or above target weight")
        if dq is not None and dq < 50:
            block_buy = True
            reasons.append("Penny add blocked — data quality below threshold")
        if liq < 35:
            block_buy = True
            flags.append("poor_liquidity")
            reasons.append("Penny add blocked — liquidity too low")
        if risk >= 70:
            block_buy = True
            reasons.append("Penny add blocked — elevated risk score")
        if mom < 40:
            block_buy = True
            reasons.append("Penny add blocked — momentum weak")

    if block_buy:
        buy_raw = 0.0
        keep_raw = max(keep_raw, 40.0)

    # Compounder: require stronger alpha for buys
    if inp.sleeve == "compounder" and alpha < 62:
        buy_raw *= 0.3
        if alpha < 55:
            block_buy = True

    # Below avg cost alone is never enough for BUY — require strong momentum + alpha
    below_cost = price < inp.avg_cost
    if below_cost:
        if mom < 55 or alpha < 58:
            buy_raw = 0.0
            if inp.sleeve == "penny" and not block_buy:
                reasons.append("Below avg cost without strong momentum/alpha — penny add blocked")
        else:
            buy_raw *= 0.6
            reasons.append("Below avg cost — reduced add sizing (needs momentum≥55 and alpha≥58)")

    # Not selling only due to volatility if score ok
    if risk >= 60 and alpha >= 58 and mom >= 50 and not overweight:
        sell_raw *= 0.6

    buy_pct, keep_pct, sell_pct = _normalize(buy_raw, keep_raw, sell_raw)

    # Final decision from highest pct unless hard override
    hard_sell = stop_loss or (overweight and risk >= 65) or (inp.sleeve == "penny" and risk >= 75)
    hard_review = dq is not None and dq < 35

    if hard_review:
        final: FinalDecision = "review"
        reasons.append("Data quality too low for actionable decision")
    elif hard_sell and sell_pct >= keep_pct:
        final = "sell"
    else:
        pairs = [("buy", buy_pct), ("keep", keep_pct), ("sell", sell_pct)]
        final = max(pairs, key=lambda x: x[1])[0]  # type: ignore[assignment]

    # Mixed signals → keep default
    if not hard_sell and not hard_review:
        spread = max(buy_pct, keep_pct, sell_pct) - sorted([buy_pct, keep_pct, sell_pct])[1]
        if spread < 8.0:
            final = "keep"
            reasons.append("Mixed signals — defaulting to KEEP")

    delta_w = inp.target_weight - inp.current_weight
    suggested_usd = round(delta_w * total_portfolio_value, 2)
    if final == "sell":
        trim_to = inp.target_weight * 0.85 if overweight else 0.0
        suggested_usd = round((trim_to - inp.current_weight) * total_portfolio_value, 2)
        if suggested_usd > -50:
            suggested_usd = round(-inp.current_weight * total_portfolio_value * 0.5, 2)

    if final == "buy" and block_buy:
        final = "keep"

    action = _suggested_action(final, suggested_usd, overweight)

    return DecisionOutput(
        final_decision=final,
        buy_pct=buy_pct,
        keep_pct=keep_pct,
        sell_pct=sell_pct,
        suggested_action=action,
        suggested_dollar_action=suggested_usd,
        reasons=reasons or ["Within normal score and risk bands"],
        risk_flags=flags,
        alpha_score=alpha,
        momentum_score=mom,
        liquidity_score=liq,
        risk_score=risk,
        data_quality_score=dq,
        current_weight=inp.current_weight,
        target_weight=inp.target_weight,
        max_allowed_weight=inp.max_allowed_weight,
        overweight_penalty=ow_penalty,
        missing_data_penalty=missing_penalty,
        stop_loss_trigger=stop_loss,
        final_buy_raw=round(buy_raw, 2),
        final_keep_raw=round(keep_raw, 2),
        final_sell_raw=round(sell_raw, 2),
        price_available=True,
    )


def max_weight_for_sleeve(sleeve: str) -> float:
    return float(SLEEVE_MAX_WEIGHT.get(sleeve, 0.08))
