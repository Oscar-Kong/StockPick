"""Trade journaling and process-quality scoring helpers."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import isfinite


@dataclass
class TradeReview:
    pnl_abs: float | None
    pnl_pct: float | None
    planned_rr: float | None
    quality_score: float
    quality_label: str
    process_good: bool
    review_note: str
    flags: list[str]


def _safe_div(a: float, b: float) -> float | None:
    if b == 0:
        return None
    out = a / b
    if not isfinite(out):
        return None
    return out


def _calc_planned_rr(side: str, entry: float, stop: float | None, target: float | None) -> float | None:
    if stop is None or target is None:
        return None
    s = (side or "long").lower()
    if s == "short":
        risk = stop - entry
        reward = entry - target
    else:
        risk = entry - stop
        reward = target - entry
    if risk <= 0:
        return None
    return _safe_div(reward, risk)


def review_trade(
    *,
    side: str,
    entry_price: float,
    exit_price: float | None,
    quantity: float | None,
    stop_loss: float | None,
    take_profit: float | None,
    thesis: str,
    tags: list[str] | None = None,
) -> TradeReview:
    clean_side = (side or "long").lower()
    direction = -1.0 if clean_side == "short" else 1.0

    pnl_pct = None
    pnl_abs = None
    if exit_price is not None and entry_price and entry_price > 0:
        pnl_pct = _safe_div((exit_price - entry_price) * direction, entry_price)
        if pnl_pct is not None:
            pnl_pct *= 100.0
        if quantity is not None:
            pnl_abs = (exit_price - entry_price) * direction * quantity

    planned_rr = (
        _calc_planned_rr(clean_side, entry_price, stop_loss, take_profit)
        if entry_price and entry_price > 0
        else None
    )

    score = 50.0
    flags: list[str] = []
    thesis_len = len((thesis or "").strip())
    tag_count = len(tags or [])

    if stop_loss is not None:
        score += 15
    else:
        score -= 14
        flags.append("no_stop_loss")

    if take_profit is not None:
        score += 8
    else:
        flags.append("no_take_profit")

    if planned_rr is not None:
        if planned_rr >= 2:
            score += 12
        elif planned_rr >= 1:
            score += 4
        else:
            score -= 10
            flags.append("low_risk_reward_plan")
    else:
        flags.append("missing_rr_plan")

    if thesis_len >= 40:
        score += 8
    elif thesis_len >= 20:
        score += 4
    else:
        score -= 8
        flags.append("weak_thesis")

    if quantity is None or quantity <= 0:
        score -= 6
        flags.append("missing_position_size")

    if tag_count >= 2:
        score += 3

    if pnl_pct is not None and pnl_pct > 0:
        if stop_loss is None or (planned_rr is not None and planned_rr < 1):
            score -= 10
            flags.append("profitable_but_process_weak")
    if pnl_pct is not None and pnl_pct < 0 and stop_loss is not None:
        score += 4
        flags.append("loss_with_risk_control")

    score = max(0.0, min(100.0, score))
    process_good = score >= 65
    if score >= 80:
        label = "A"
    elif score >= 65:
        label = "B"
    elif score >= 50:
        label = "C"
    else:
        label = "D"

    if pnl_pct is None:
        note = "Trade is open. Process score focuses on planning quality."
    elif pnl_pct >= 0 and process_good:
        note = "Profitable trade with acceptable process quality."
    elif pnl_pct >= 0 and not process_good:
        note = "Profitable outcome, but setup and risk process were weak."
    elif pnl_pct < 0 and process_good:
        note = "Losing trade, but process quality was solid. Keep execution disciplined."
    else:
        note = "Losing trade with weak process. Review setup and risk rules."

    return TradeReview(
        pnl_abs=round(pnl_abs, 4) if pnl_abs is not None else None,
        pnl_pct=round(pnl_pct, 4) if pnl_pct is not None else None,
        planned_rr=round(planned_rr, 4) if planned_rr is not None else None,
        quality_score=round(score, 2),
        quality_label=label,
        process_good=process_good,
        review_note=note,
        flags=flags,
    )


from utils.datetime_util import parse_api_datetime


def parse_iso_datetime(value: str | None) -> datetime | None:
    return parse_api_datetime(value)
