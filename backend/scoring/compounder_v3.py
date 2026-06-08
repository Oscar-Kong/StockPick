"""Compounder sleeve expanded factors — valuation percentiles, FCF, adjusted EPS."""
from __future__ import annotations

from scoring.fundamental import revenue_eps_consistency_score, roic_margin_stability_score
from scoring.metrics import clip100, safe_float
from scoring.technical import smooth_growth_score


def _invert_score(score: float) -> float:
    return max(0.0, min(100.0, 100.0 - score))


def _pe_score(pe: float) -> float:
    if pe <= 0:
        return 40.0
    return _invert_score(clip100(pe, 8, 45))


def rev_growth_score(info: dict, fundamentals: dict) -> float:
    rev = safe_float(info.get("revenueGrowth") or fundamentals.get("revenue_growth"))
    return clip100(rev, 0.0, 0.25)


def eps_growth_score(info: dict, fundamentals: dict) -> float:
    eps = safe_float(info.get("earningsGrowth") or fundamentals.get("earnings_growth"))
    return clip100(eps, 0.0, 0.30)


def fcf_yield_score(info: dict, fundamentals: dict) -> float:
    fcf = safe_float(info.get("freeCashflow") or fundamentals.get("free_cash_flow"))
    mcap = safe_float(info.get("marketCap") or fundamentals.get("market_cap"))
    if mcap <= 0:
        return 50.0
    yld = fcf / mcap
    return clip100(yld, 0.0, 0.08)


def debt_ratio_score(info: dict, fundamentals: dict) -> float:
    debt = safe_float(info.get("debtToEquity") or fundamentals.get("debt_to_equity"))
    return _invert_score(clip100(debt, 20, 180))


def goodwill_ratio_score(info: dict, fundamentals: dict) -> float:
    gw = safe_float(info.get("goodwill") or fundamentals.get("goodwill"))
    assets = safe_float(info.get("totalAssets") or fundamentals.get("total_assets"))
    if assets <= 0:
        return 60.0
    ratio = gw / assets
    return _invert_score(clip100(ratio, 0.05, 0.45))


def margin_combo_score(info: dict, fundamentals: dict) -> float:
    gross = safe_float(info.get("grossMargins") or fundamentals.get("gross_margin"))
    op = safe_float(info.get("operatingMargins") or fundamentals.get("operating_margin"))
    return max(0.0, min(100.0, 50 + gross * 80 + op * 60))


def dividend_growth_proxy(info: dict) -> float:
    dy = safe_float(info.get("dividendYield"))
    payout = safe_float(info.get("payoutRatio"))
    score = 50.0
    if 0.01 <= dy <= 0.04:
        score += 15
    if 0 < payout <= 0.6:
        score += 10
    if dy > 0.06:
        score -= 10
    return max(0.0, min(100.0, score))


def valuation_percentile_scores(info: dict, fundamentals: dict) -> dict[str, float]:
    pe = safe_float(fundamentals.get("pe_ratio") or info.get("trailingPE"))
    pb = safe_float(fundamentals.get("pb_ratio") or info.get("priceToBook"))
    ps = safe_float(fundamentals.get("ps_ratio") or info.get("priceToSalesTrailing12Months"))
    return {
        "pe_pct_5y": _pe_score(pe),
        "pb_pct_5y": _invert_score(clip100(pb, 0.8, 8.0)) if pb > 0 else 50.0,
        "ps_pct_5y": _invert_score(clip100(ps, 0.5, 12.0)) if ps > 0 else 50.0,
    }


def adjusted_eps_score(info: dict, fundamentals: dict) -> float:
    eps = safe_float(info.get("trailingEps") or fundamentals.get("eps"))
    if eps == 0:
        return revenue_eps_consistency_score(info, fundamentals)
    one_off = safe_float(info.get("extraordinaryItems") or fundamentals.get("extraordinary_items"))
    if abs(eps) > 0 and abs(one_off) / abs(eps) > 0.5:
        return 35.0
    return clip100(eps, 0.5, 8.0)


def compounder_expanded_scores(
    df,
    info: dict,
    fundamentals: dict,
) -> dict[str, float]:
    val = valuation_percentile_scores(info, fundamentals)
    smooth = smooth_growth_score(df) if df is not None and not getattr(df, "empty", True) else 50.0
    return {
        "rev_growth": rev_growth_score(info, fundamentals),
        "eps_growth": eps_growth_score(info, fundamentals),
        "roic": roic_margin_stability_score(info, fundamentals),
        "fcf_yield": fcf_yield_score(info, fundamentals),
        "debt_ratio": debt_ratio_score(info, fundamentals),
        "goodwill_ratio": goodwill_ratio_score(info, fundamentals),
        "gross_operating_margin": margin_combo_score(info, fundamentals),
        "dividend_growth": dividend_growth_proxy(info),
        "adjusted_eps": adjusted_eps_score(info, fundamentals),
        "smooth_growth": smooth,
        **val,
    }
