"""Fundamental scoring for medium and compounder buckets."""
from __future__ import annotations

from typing import Any

from config import COMPOUNDER_MIN_REVENUE_GROWTH


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


def _safe(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def revenue_eps_consistency_score(info: dict, fundamentals: dict) -> float:
    rev_growth = _safe(info.get("revenueGrowth"))
    eps_growth = _safe(info.get("earningsGrowth"))
    pe = _safe(fundamentals.get("pe_ratio"), default=25)

    score = 50.0
    if rev_growth > 0.15:
        score += 25
    elif rev_growth > 0.08:
        score += 15
    elif rev_growth > 0.05:
        score += 8
    elif rev_growth < 0:
        score -= 20

    if eps_growth > 0.10:
        score += 15
    elif eps_growth > 0:
        score += 5
    elif eps_growth < 0:
        score -= 10

    if 10 <= pe <= 35:
        score += 5
    elif pe > 60:
        score -= 10

    return _clamp(score)


def roic_margin_stability_score(info: dict, fundamentals: dict) -> float:
    margin = _safe(info.get("profitMargins"))
    if margin == 0:
        margin = _safe(fundamentals.get("profit_margin"))
    roe = _safe(info.get("returnOnEquity"))
    if roe == 0:
        roe = _safe(fundamentals.get("return_on_equity"))
    debt = _safe(info.get("debtToEquity"))
    if debt == 0:
        debt = _safe(fundamentals.get("debt_to_equity"))

    score = 50.0
    if margin > 0.20:
        score += 20
    elif margin > 0.10:
        score += 10
    elif margin < 0:
        score -= 25

    if roe > 0.20:
        score += 15
    elif roe > 0.12:
        score += 8
    elif roe < 0:
        score -= 15

    if debt < 50:
        score += 10
    elif debt > 150:
        score -= 15
    elif debt > 100:
        score -= 5

    return _clamp(score)


def moat_proxy_score(info: dict, fundamentals: dict) -> float:
    op_margin = _safe(fundamentals.get("operating_margin"))
    if op_margin == 0:
        op_margin = _safe(info.get("ebitdaMargins"))
    fcf = _safe(info.get("freeCashflow"))
    sector = (info.get("sector") or fundamentals.get("sector") or "").lower()

    score = 50.0
    if op_margin > 0.25:
        score += 20
    elif op_margin > 0.15:
        score += 10

    if fcf > 0:
        score += 15
    elif fcf < 0:
        score -= 15

    if sector in ("technology", "healthcare", "consumer defensive"):
        score += 5

    return _clamp(score)


def quality_filter_passes(info: dict, fundamentals: dict, min_market_cap: float) -> bool:
    market_cap = _safe(info.get("marketCap"))
    if market_cap == 0:
        market_cap = _safe(fundamentals.get("market_cap"))
    if market_cap > 0 and market_cap < min_market_cap:
        return False

    rev_growth = _safe(info.get("revenueGrowth"), default=-999)
    eps_growth = _safe(info.get("earningsGrowth"), default=-999)
    # Allow pass when growth data is missing if large cap
    if rev_growth == -999 and eps_growth == -999:
        return market_cap == 0 or market_cap >= min_market_cap

    if rev_growth < COMPOUNDER_MIN_REVENUE_GROWTH and eps_growth < COMPOUNDER_MIN_REVENUE_GROWTH:
        return False

    fcf = info.get("freeCashflow")
    if fcf is not None and _safe(fcf) < 0:
        debt = _safe(info.get("debtToEquity"))
        if debt > 200:
            return False

    return True
