"""Fundamental scoring helpers with explicit missing-data handling."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from config import COMPOUNDER_MIN_REVENUE_GROWTH


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


def _optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if out != out:  # NaN
        return None
    return out


@dataclass
class FactorScoreResult:
    score: float
    missing_fields: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def __float__(self) -> float:
        return self.score


def revenue_eps_consistency_score(info: dict, fundamentals: dict) -> FactorScoreResult:
    missing: list[str] = []
    rev_growth = _optional_float(info.get("revenueGrowth"))
    if rev_growth is None:
        rev_growth = _optional_float(fundamentals.get("revenue_growth"))
    if rev_growth is None:
        missing.append("revenue_growth")

    eps_growth = _optional_float(info.get("earningsGrowth"))
    if eps_growth is None:
        eps_growth = _optional_float(fundamentals.get("earnings_growth"))
    if eps_growth is None:
        missing.append("eps_growth")

    pe = _optional_float(fundamentals.get("pe_ratio"))
    if pe is None:
        pe = _optional_float(info.get("trailingPE"))

    score = 50.0
    if rev_growth is not None:
        if rev_growth > 0.15:
            score += 25
        elif rev_growth > 0.08:
            score += 15
        elif rev_growth > 0.05:
            score += 8
        elif rev_growth < 0:
            score -= 20
    if eps_growth is not None:
        if eps_growth > 0.10:
            score += 15
        elif eps_growth > 0:
            score += 5
        elif eps_growth < 0:
            score -= 10
    if pe is not None:
        if 10 <= pe <= 35:
            score += 5
        elif pe > 60:
            score -= 10

    return FactorScoreResult(score=_clamp(score), missing_fields=missing)


def roic_margin_stability_score(info: dict, fundamentals: dict) -> FactorScoreResult:
    missing: list[str] = []
    margin = _optional_float(info.get("profitMargins"))
    if margin is None:
        margin = _optional_float(fundamentals.get("profit_margin"))
    if margin is None:
        missing.append("profit_margin")

    roe = _optional_float(info.get("returnOnEquity"))
    if roe is None:
        roe = _optional_float(fundamentals.get("return_on_equity"))
    if roe is None:
        missing.append("return_on_equity")

    debt = _optional_float(info.get("debtToEquity"))
    if debt is None:
        debt = _optional_float(fundamentals.get("debt_to_equity"))
    if debt is None:
        missing.append("debt_to_equity")

    score = 50.0
    if margin is not None:
        if margin > 0.20:
            score += 20
        elif margin > 0.10:
            score += 10
        elif margin < 0:
            score -= 25
    if roe is not None:
        if roe > 0.20:
            score += 15
        elif roe > 0.12:
            score += 8
        elif roe < 0:
            score -= 15
    if debt is not None:
        if debt < 50:
            score += 10
        elif debt > 150:
            score -= 15
        elif debt > 100:
            score -= 5

    return FactorScoreResult(score=_clamp(score), missing_fields=missing)


def moat_proxy_score(info: dict, fundamentals: dict) -> FactorScoreResult:
    missing: list[str] = []
    op_margin = _optional_float(fundamentals.get("operating_margin"))
    if op_margin is None:
        op_margin = _optional_float(info.get("operatingMargins"))
    if op_margin is None:
        op_margin = _optional_float(info.get("ebitdaMargins"))
    if op_margin is None:
        missing.append("operating_margin")

    fcf = _optional_float(info.get("freeCashflow"))
    if fcf is None:
        fcf = _optional_float(fundamentals.get("free_cash_flow"))
    if fcf is None:
        missing.append("free_cash_flow")

    sector = (info.get("sector") or fundamentals.get("sector") or "").lower()
    if not sector:
        missing.append("sector")

    score = 50.0
    if op_margin is not None:
        if op_margin > 0.25:
            score += 20
        elif op_margin > 0.15:
            score += 10
    if fcf is not None:
        if fcf > 0:
            score += 15
        elif fcf < 0:
            score -= 15
    if sector in ("technology", "healthcare", "consumer defensive"):
        score += 5

    return FactorScoreResult(score=_clamp(score), missing_fields=missing)


def quality_filter_passes(info: dict, fundamentals: dict, min_market_cap: float) -> bool:
    market_cap = _optional_float(info.get("marketCap"))
    if market_cap is None:
        market_cap = _optional_float(fundamentals.get("market_cap"))
    if market_cap is not None and market_cap > 0 and market_cap < min_market_cap:
        return False

    rev_growth = _optional_float(info.get("revenueGrowth"))
    if rev_growth is None:
        rev_growth = _optional_float(fundamentals.get("revenue_growth"))
    eps_growth = _optional_float(info.get("earningsGrowth"))
    if eps_growth is None:
        eps_growth = _optional_float(fundamentals.get("earnings_growth"))

    if rev_growth is None and eps_growth is None:
        return market_cap is None or market_cap >= min_market_cap

    if rev_growth is not None and eps_growth is not None:
        if rev_growth < COMPOUNDER_MIN_REVENUE_GROWTH and eps_growth < COMPOUNDER_MIN_REVENUE_GROWTH:
            return False

    fcf = _optional_float(info.get("freeCashflow"))
    if fcf is None:
        fcf = _optional_float(fundamentals.get("free_cash_flow"))
    if fcf is not None and fcf < 0:
        debt = _optional_float(info.get("debtToEquity"))
        if debt is None:
            debt = _optional_float(fundamentals.get("debt_to_equity"))
        if debt is not None and debt > 200:
            return False

    return True
