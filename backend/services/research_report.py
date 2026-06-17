"""Structured AI research report — quant v2 pipeline with narrative generation."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from config import AI_REPORT_SCHEMA, FACTOR_MODEL_VERSION, POSITION_SIZING_V2, STRATEGY_VERSION
from core.sleeve import normalize_sleeve
from data.cache import Cache
from data.price_service import PriceService
from data.reconciler import DataReconciler
from models.schemas import Bucket
from scoring.structure_analysis import long_term_structure
from scoring.technical import breakout_score, relative_strength_vs_spy, trend_score
from scoring.valuation import valuation_warnings
from services.quant_risk_sizing_service import build_position_sizing, build_unified_risk
from services.quant_v2_service import build_v2_score
from services.report_llm_context import build_quant_report_context, system_rating_from_score, _serialize
from services.report_narrative import DISCLAIMER_FOOTER, generate_report_narrative

logger = logging.getLogger(__name__)
REPORT_CACHE_TTL = 86400 * 2


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _horizon_for_sleeve(sleeve: str) -> str:
    return {"penny": "3-10 days", "compounder": "3-10+ years"}.get(sleeve, "3-10 days")


def build_research_report(
    symbol: str,
    sleeve: str | Bucket | None = None,
    *,
    portfolio_symbols: list[str] | None = None,
) -> dict[str, Any]:
    if AI_REPORT_SCHEMA != "v2":
        return {"error": "AI_REPORT_SCHEMA is not v2", "schema_version": AI_REPORT_SCHEMA}

    sym = symbol.upper()
    raw = sleeve.value if isinstance(sleeve, Bucket) else sleeve
    sleeve_val = normalize_sleeve(raw)
    score = build_v2_score(sym, sleeve_val, validate_parity=False)
    if isinstance(score, dict) and score.get("error"):
        return {"symbol": sym, "error": score["error"]}

    rec = DataReconciler().reconcile(sym)
    info, fundamentals, _ = DataReconciler().get_canonical_fundamentals(sym)
    ps = PriceService()
    hist = ps.get_history(sym, period="2y")
    spy = ps.get_spy_history(period="1y")
    structure = long_term_structure(hist)
    tech = {
        "trend_score": round(trend_score(hist), 1) if not hist.empty else None,
        "breakout_score": round(breakout_score(hist), 1) if not hist.empty else None,
        "rs_vs_spy": round(relative_strength_vs_spy(hist, spy), 1)
        if not hist.empty and not spy.empty
        else None,
    }
    warnings = valuation_warnings(info, fundamentals)

    final_rating = system_rating_from_score(score, sleeve=sleeve_val)
    final_rating["horizon"] = _horizon_for_sleeve(sleeve_val)

    risk_v2 = build_unified_risk(sym, sleeve_val, score_result=score)
    sizing_v2 = score.position_sizing if score.position_sizing else (
        build_position_sizing(sym, sleeve_val, score_result=score) if POSITION_SIZING_V2 else None
    )

    factors = [
        {
            "factor_id": f.factor_id,
            "value": f.norm_score,
            "weight": f.weight,
            "contribution": f.contribution,
            "ic_30d": None,
            "status": "active",
        }
        for f in score.factors
    ]

    llm_context = build_quant_report_context(
        score,
        sleeve=sleeve_val,
        reconcile=rec,
        portfolio_symbols=portfolio_symbols,
    )
    narrative = generate_report_narrative(llm_context)

    report = {
        "schema_version": "2.0.0",
        "symbol": sym,
        "sleeve": sleeve_val,
        "as_of": _now_iso(),
        "final_rating": {
            "action": final_rating["action"],
            "conviction": final_rating["conviction"],
            "composite_score": final_rating["composite_score"],
            "horizon": final_rating["horizon"],
            "system_label": final_rating.get("system_label"),
            "gates": final_rating.get("gates", []),
        },
        "executive_summary": narrative["executive_summary"],
        "investment_thesis": narrative["investment_thesis"],
        "uncertainty": narrative.get("uncertainty", []),
        "what_would_change_my_mind": narrative.get("what_would_change_my_mind", []),
        "data_quality_limitations": narrative.get("data_quality_limitations", []),
        "key_catalysts": _catalysts(score.metrics, sleeve_val),
        "risks": {
            "risk_score": risk_v2.risk_index if not isinstance(risk_v2, dict) else score.risk.deduction_pts,
            "macro": risk_v2.macro if not isinstance(risk_v2, dict) else [],
            "company": risk_v2.company if not isinstance(risk_v2, dict) else [],
            "events": risk_v2.events if not isinstance(risk_v2, dict) else [],
            "score_deductions": risk_v2.score_deductions if not isinstance(risk_v2, dict) else [],
        },
        "quantitative_analysis": {
            "composite_score": score.score,
            "raw_score": score.attribution.raw_score,
            "data_quality_score": rec.quality_score if rec else None,
            "regime": score.market_regime or "neutral",
            "factor_contributions": factors,
            "attribution": _serialize(score.attribution) or {},
        },
        "fundamental_analysis": {
            "revenue_growth_ttm": info.get("revenueGrowth"),
            "eps_growth_ttm": info.get("earningsGrowth"),
            "roic": info.get("returnOnEquity"),
            "fcf_yield": None,
            "debt_to_equity": info.get("debtToEquity"),
            "adjusted_earnings_flag": True,
            "industry_percentile_summary": info.get("sector") or "Sector data from provider snapshot",
        },
        "technical_analysis": {
            **tech,
            "pct_from_52w_high": structure.get("pct_from_high"),
            "structure": structure.get("weekly_trend") or structure.get("ma200_position"),
        },
        "valuation_analysis": {
            "pe_percentile_5y": fundamentals.get("pe_ratio"),
            "pb_percentile_5y": fundamentals.get("pb_ratio"),
            "ps_percentile_5y": fundamentals.get("ps_ratio"),
            "vs_industry": "heuristic band — enable FMP peers for industry ranks",
            "warnings": warnings,
            **(_serialize(score.valuation) or {}),
        },
        "diagnostics_summary": llm_context.get("diagnostics_summary"),
        "backtest_summary": llm_context.get("backtest_summary"),
        "factor_exposure_summary": llm_context.get("factor_exposure_summary"),
        "earnings_setup": score.earnings_setup or {},
        "similar_signal_backtest": _serialize(score.similar_signal),
        "recommendation": _serialize(score.recommendation),
        "position_sizing": _sizing_dict(sizing_v2),
        "metadata": {
            "model_version": FACTOR_MODEL_VERSION,
            "strategy_version": STRATEGY_VERSION,
            "data_sources": ["quant_v2", "reconciled_fundamentals", "price_history"],
            "llm_model": narrative.get("llm_model"),
            "narrative_source": narrative.get("source", "rules"),
            "disclaimer": narrative.get("disclaimer") or DISCLAIMER_FOOTER,
            "rating_source": final_rating.get("source"),
        },
        "legacy_bucket": raw if isinstance(raw, str) else (sleeve.value if isinstance(sleeve, Bucket) else None),
        "v1_score": score.score,
    }

    Cache().set(_cache_key(sym, sleeve_val), report, REPORT_CACHE_TTL)
    return report


def _cache_key(symbol: str, sleeve: str) -> str:
    return f"report:{symbol}:{sleeve}"


def _catalysts(metrics: dict, sleeve: str) -> list[dict]:
    out: list[dict] = []
    days = metrics.get("days_until_earnings")
    if days is not None and days <= 30:
        out.append(
            {
                "event": "Earnings report",
                "timing": f"~{int(days)} days",
                "impact": "high" if days <= 7 else "medium",
            }
        )
    if sleeve == "penny" and metrics.get("volume_ratio"):
        out.append(
            {
                "event": "Volume activity vs baseline",
                "timing": "near-term",
                "impact": "medium",
            }
        )
    if not out:
        out.append({"event": "Monitor price/volume confirmation", "timing": "ongoing", "impact": "low"})
    return out


def _sizing_dict(sizing: Any) -> dict:
    if sizing is None or isinstance(sizing, dict):
        return {
            "recommended_weight_pct": 0.0,
            "max_weight_pct": 0.0,
            "stop_loss_pct": 0.0,
            "portfolio_allocation_pct": 0.0,
            "rationale": "Enable POSITION_SIZING_V2 for allocation guidance",
            "kelly_fraction": None,
        }
    return {
        "recommended_weight_pct": sizing.recommended_weight_pct,
        "max_weight_pct": sizing.max_weight_pct,
        "stop_loss_pct": sizing.stop_loss_pct,
        "portfolio_allocation_pct": sizing.portfolio_allocation_pct,
        "rationale": sizing.rationale,
        "kelly_fraction": None,
    }


def get_cached_report(symbol: str, sleeve: str | Bucket | None = None) -> dict | None:
    sym = symbol.upper()
    raw = sleeve.value if isinstance(sleeve, Bucket) else sleeve
    sleeve_val = normalize_sleeve(raw)
    cached = Cache().get(_cache_key(sym, sleeve_val))
    if cached:
        return cached
    # Legacy cache keys from pre-consolidation reports
    legacy = Cache().get(f"report_v2:{sym}:{sleeve_val}")
    if legacy:
        return legacy
    if raw and str(raw).lower() == "medium":
        return Cache().get(f"report_v2:{sym}:medium") or Cache().get(f"report:{sym}:penny")
    return None


# Temporary aliases for callers not yet updated
build_research_report_v2 = build_research_report
get_cached_report_v2 = get_cached_report
