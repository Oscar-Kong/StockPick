"""Structured 8-section stock research report."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from config import FMP_API_KEY, FINNHUB_API_KEY, FRED_API_KEY, PRIMARY_FUNDAMENTALS_SOURCE
from data.cache import Cache
from data.earnings import get_next_earnings_date
from data.finnhub_client import FinnhubClient
from data.fmp_client import FMPClient
from data.fred_client import FredClient
from data.price_service import PriceService
from data.reconciler import DataReconciler
from models.schemas import Bucket
from scoring.sector_strength import sector_relative_strength
from scoring.structure_analysis import fair_value_zones, long_term_structure
from scoring.technical import relative_strength_vs_spy, trend_score
from scoring.valuation import valuation_warnings
from services.alerts import compute_alerts

logger = logging.getLogger(__name__)

REPORT_CACHE_TTL = 86400 * 3


def _safe(v: Any, default: float | None = None) -> float | None:
    if v is None:
        return default
    try:
        f = float(v)
        return None if f != f else f
    except (TypeError, ValueError):
        return default


def _fetch_full_info(symbol: str) -> dict[str, Any]:
    info: dict[str, Any] = {}
    rec_info, _, _ = DataReconciler().get_canonical_fundamentals(symbol)
    info.update(rec_info)
    if FMP_API_KEY and PRIMARY_FUNDAMENTALS_SOURCE == "fmp":
        fmp = FMPClient().get_fundamentals_bundle(symbol)
        info = {**info, **fmp}
    return info


def _industry_positioning(info: dict, rev_growth: float | None, rs_spy: float | None) -> dict:
    rg = rev_growth if rev_growth is not None else _safe(info.get("revenueGrowth"))
    if rg is None:
        growth_stage = "unknown"
    elif rg > 0.15:
        growth_stage = "growth"
    elif rg > 0.03:
        growth_stage = "mature"
    else:
        growth_stage = "declining"

    mcap = _safe(info.get("marketCap")) or 0
    margin = _safe(info.get("profitMargins")) or _safe(info.get("profit_margin")) or 0
    if mcap > 50e9 and margin > 0.15:
        competitive = "leader"
    elif mcap > 5e9:
        competitive = "mid-tier"
    else:
        competitive = "niche"

    sector_strength = "neutral"
    if rs_spy is not None:
        if rs_spy >= 60:
            sector_strength = "strong_vs_market"
        elif rs_spy <= 40:
            sector_strength = "weak_vs_market"

    macro = "Macro data not configured (add FRED_API_KEY for regime context)."
    if FRED_API_KEY:
        score = FredClient().macro_regime_score()
        if score >= 60:
            macro = "Supportive macro backdrop (rates/growth regime score favorable)."
        elif score <= 40:
            macro = "Challenging macro backdrop — tighter conditions for risk assets."
        else:
            macro = "Mixed macro backdrop — sector selection matters more than beta."

    sector = info.get("sector") or info.get("industry") or "Unknown"
    trending = sector_strength in ("strong_vs_market",) and growth_stage == "growth"

    return {
        "industry_growth_stage": growth_stage,
        "competitive_position": competitive,
        "sector": sector,
        "sector_strength_vs_market": sector_strength,
        "sector_on_trend": trending,
        "macro_background": macro,
    }


def _fundamentals_section(info: dict, fundamentals: dict, warnings: list[str]) -> dict:
    pe = _safe(info.get("trailingPE")) or _safe(fundamentals.get("pe_ratio"))
    pb = _safe(fundamentals.get("price_to_book")) or _safe(info.get("priceToBook"))
    roe = _safe(info.get("returnOnEquity")) or _safe(fundamentals.get("roe"))
    gross = _safe(info.get("grossMargins"))
    margin = _safe(info.get("profitMargins")) or _safe(fundamentals.get("profit_margin"))
    rev_g = _safe(info.get("revenueGrowth"))
    eps_g = _safe(info.get("earningsGrowth"))
    fcf = _safe(info.get("freeCashflow"))
    debt = _safe(info.get("totalDebt"))
    cash = _safe(info.get("totalCash"))

    pe_note = "Compare to industry average when FMP/AV keys enabled for peer data."
    if pe is not None:
        if pe > 40:
            pe_note = "Above typical market multiple — growth must justify."
        elif 12 <= pe <= 25:
            pe_note = "Within a reasonable range vs broad market norms."
        elif pe < 0:
            pe_note = "Negative earnings — P/E not meaningful."

    return {
        "valuation": {
            "pe": pe,
            "pb": pb,
            "pe_vs_history_note": pe_note,
            "peg": _safe(fundamentals.get("peg_ratio")),
        },
        "profitability": {
            "roe": roe,
            "gross_margin": gross,
            "net_margin": margin,
        },
        "growth": {
            "revenue_yoy": rev_g,
            "earnings_yoy": eps_g,
        },
        "financial_health": {
            "free_cash_flow": fcf,
            "total_debt": debt,
            "cash": cash,
            "debt_to_equity": _safe(info.get("debtToEquity")) or _safe(fundamentals.get("debt_to_equity")),
        },
        "flags": warnings,
    }


def _institutional_section(info: dict, df) -> dict:
    inst_pct = _safe(info.get("heldPercentInstitutions"))
    if inst_pct is not None and inst_pct <= 1:
        inst_pct = inst_pct * 100

    flow = "unknown"
    if df is not None and not df.empty and len(df) >= 40:
        ret_30 = float(df["close"].iloc[-1] / df["close"].iloc[-30] - 1)
        vol_r = float(df["volume"].tail(30).mean())
        vol_p = float(df["volume"].iloc[-60:-30].mean())
        if ret_30 > 0.05 and vol_r > vol_p:
            flow = "positive_30d"
        elif ret_30 < -0.05 and vol_r > vol_p:
            flow = "distribution_30d"
        else:
            flow = "mixed_30d"

    return {
        "institutional_ownership_pct": round(inst_pct, 1) if inst_pct is not None else None,
        "institutional_activity_note": (
            "Detailed 13F buy/sell requires premium data feed — using price/volume proxy."
        ),
        "capital_flow_30d": flow,
        "liquidity_note": "See volume_signal in technical structure for accumulation/distribution.",
    }


def _sentiment_section(info: dict, metrics: dict, news_headlines: list[str]) -> dict:
    target = _safe(info.get("targetMeanPrice"))
    price = _safe(info.get("currentPrice")) or _safe(info.get("price"))
    rec = info.get("recommendationKey") or "none"
    analysts = info.get("numberOfAnalystOpinions")

    target_range = None
    if target and price:
        target_range = f"Consensus ~${target:.2f} vs price ${price:.2f} ({((target/price)-1)*100:+.1f}%)"

    rsi_proxy = metrics.get("news_score", 50)
    if isinstance(rsi_proxy, (int, float)):
        if rsi_proxy >= 65:
            sentiment = "overheated"
        elif rsi_proxy <= 35:
            sentiment = "oversold"
        else:
            sentiment = "neutral"
    else:
        sentiment = "neutral"

    return {
        "earnings_date": metrics.get("earnings_date"),
        "days_until_earnings": metrics.get("days_until_earnings"),
        "news_headlines": news_headlines[:5],
        "analyst_consensus": rec,
        "analyst_count": analysts,
        "price_target_note": target_range,
        "market_sentiment": sentiment,
    }


def _strategic_outlook(
    bucket: str,
    score: float,
    zones: dict,
    structure: dict,
    risks: list[str],
    warnings: list[str],
) -> dict:
    top_risks = risks[:3]
    while len(top_risks) < 3:
        top_risks.append("Insufficient data — refresh after API keys configured.")

    zone = zones.get("current_zone", "fair")
    weekly = structure.get("weekly_trend", "sideways")

    if bucket == "compounder" and score >= 65 and zone != "overvalued":
        conclusion = "long_term_accumulation"
        strategy = (
            "Favor accumulating on pullbacks toward major support / undervalued zone; "
            "reduce adds if price enters overvalued zone."
        )
    elif bucket in ("medium", "penny") and score >= 60 and weekly == "bullish":
        conclusion = "swing_hold"
        strategy = (
            "Swing-friendly structure — consider exposure between support and fair-value zone; "
            "take profit into resistance / overvalued zone."
        )
    elif score < 45 or zone == "overvalued" or weekly == "bearish":
        conclusion = "avoid"
        strategy = (
            "Weak quant + technical profile — wait for better structure or valuation; "
            "no precise entry levels provided."
        )
    else:
        conclusion = "swing_hold"
        strategy = (
            "Mixed profile — only size positions inside fair-value zone with tight risk "
            "awareness around earnings and resistance."
        )

    return {
        "top_risks": top_risks,
        "conclusion": conclusion,
        "strategy_guidance": strategy,
        "assigned_bucket": bucket,
        "quant_score": score,
    }


def build_research_report(symbol: str, bucket: Bucket | None = None) -> dict[str, Any]:
    from services.watchlist_scanner import analyze_symbol

    sym = symbol.upper()
    ps = PriceService()
    info = _fetch_full_info(sym)
    info_rec, fundamentals, rec = DataReconciler().get_canonical_fundamentals(sym)

    assigned_bucket = bucket
    bucket_choice: Bucket | str = assigned_bucket if assigned_bucket else "auto"
    result, err = analyze_symbol(sym, bucket_choice)
    if err or result is None:
        return {"symbol": sym, "error": err or "Could not analyze symbol", "generated_at": _now()}

    assigned = result.bucket
    metrics = result.metrics or {}
    warnings = valuation_warnings(info_rec, fundamentals) + list(result.valuation_warnings or [])

    hist = ps.get_history(sym, period="2y")
    spy = ps.get_spy_history(period="1y")
    structure = long_term_structure(hist)
    rs = relative_strength_vs_spy(hist, spy) if not hist.empty and not spy.empty else None

    pe = _safe(info.get("trailingPE")) or _safe(fundamentals.get("pe_ratio"))
    rev_g = _safe(info.get("revenueGrowth"))
    zones = fair_value_zones(
        structure.get("price", result.price),
        structure.get("low_52w", result.price * 0.8),
        structure.get("high_52w", result.price * 1.2),
        pe,
        rev_g,
    )

    news_headlines: list[str] = metrics.get("news_headlines") or []
    if FINNHUB_API_KEY and not news_headlines:
        news_headlines = FinnhubClient().news_summary(sym).get("headlines", [])

    industry = _industry_positioning(info, rev_g, rs)
    fundamentals_block = _fundamentals_section(info, fundamentals, warnings)
    institutional = _institutional_section(info, hist)

    risk_pool = list(warnings)
    if industry["industry_growth_stage"] == "declining":
        risk_pool.append("Industry/growth: declining revenue trend")
    if structure.get("ma200_position") == "below":
        risk_pool.append("Technical: trading below 200-day MA")
    if rec.quality_score < 50:
        risk_pool.append("Data: limited cross-source verification")

    try:
        from services.openbb_integration import enrich_research_risks

        risk_pool = enrich_research_risks(sym, risk_pool)
    except Exception as exc:
        logger.debug("OpenBB research risks skipped for %s: %s", sym, exc)

    outlook = _strategic_outlook(
        assigned.value,
        result.score,
        zones,
        structure,
        risk_pool,
        warnings,
    )

    alerts = compute_alerts(
        sym,
        bucket=assigned.value,
        score=result.score,
        days_until_earnings=metrics.get("days_until_earnings"),
        valuation_warnings=warnings,
        data_quality_score=rec.quality_score,
        reconcile_flags=rec.flags,
        last_scanned_at=datetime.utcnow().isoformat(),
        openbb_risk_flags=metrics.get("openbb_risk_flags"),
        openbb_governance_score=metrics.get("openbb_governance_score"),
    )

    report = {
        "symbol": sym,
        "generated_at": _now(),
        "assigned_bucket": assigned.value,
        "quant_score": result.score,
        "1_overview": {
            "symbol": sym,
            "company_name": info.get("shortName") or info.get("name") or fundamentals.get("name"),
            "sector": info.get("sector") or fundamentals.get("sector"),
            "industry": info.get("industry") or fundamentals.get("industry"),
            "price": result.price,
            "market_cap": _safe(info.get("marketCap")) or _safe(fundamentals.get("market_cap")),
            "high_52w": structure.get("high_52w"),
            "low_52w": structure.get("low_52w"),
            "business_summary": (info.get("longBusinessSummary") or "")[:1200] or (
                f"{info.get('shortName', sym)} — summary unavailable without extended data fetch."
            ),
        },
        "2_industry_positioning": industry,
        "3_fundamentals": fundamentals_block,
        "4_technical_structure": {
            **structure,
            "daily_trend_score": round(trend_score(hist), 1) if not hist.empty else None,
            "rs_vs_spy": round(rs, 1) if rs is not None else None,
        },
        "5_institutional_liquidity": institutional,
        "6_news_sentiment": _sentiment_section(info, metrics, news_headlines),
        "7_valuation_zones": zones,
        "8_risk_outlook": outlook,
        "alerts": alerts,
        "data_quality_score": rec.quality_score,
        "alignment_notes": _alignment_checklist(),
    }

    Cache().set(f"report:{sym}", report, REPORT_CACHE_TTL)
    return report


def _alignment_checklist() -> dict[str, str]:
    return {
        "1_overview": "covered",
        "2_industry": "heuristic (full peer data needs FMP)",
        "3_fundamentals": "covered; industry avg PE needs FMP",
        "4_technical": "daily+weekly+monthly; use chart for visual confirm",
        "5_institutional": "ownership signal from provider aggregate; 13F detail needs paid feed",
        "6_news": "headlines+earnings; analyst targets when available",
        "7_zones": "range-based zones — not exact entries",
        "8_outlook": "zone-based guidance only",
    }


def _now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def get_cached_report(symbol: str) -> dict | None:
    return Cache().get(f"report:{symbol.upper()}")
