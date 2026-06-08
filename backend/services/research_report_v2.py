"""AI research report v2 — structured JSON aligned with ai_research_report_v2.schema.json."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from config import AI_REPORT_SCHEMA, FACTOR_MODEL_VERSION, POSITION_SIZING_V2, STRATEGY_VERSION
from data.cache import Cache
from data.price_service import PriceService
from data.reconciler import DataReconciler
from models.schemas import Bucket
from scoring.structure_analysis import fair_value_zones, long_term_structure
from scoring.technical import breakout_score, relative_strength_vs_spy, trend_score
from scoring.valuation import valuation_warnings
from services.quant_risk_sizing_service import build_position_sizing, build_unified_risk
from services.quant_v2_service import build_v2_score

logger = logging.getLogger(__name__)
REPORT_V2_CACHE_TTL = 86400 * 2


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _rating_from_score(score: float) -> tuple[str, float]:
    if score >= 80:
        return "strong_buy", score
    if score >= 65:
        return "buy", score
    if score >= 45:
        return "hold", score
    if score >= 30:
        return "reduce", score
    return "avoid", score


def _horizon_for_sleeve(sleeve: str) -> str:
    return {"penny": "3-10 days", "medium": "4-8 weeks", "compounder": "3-10+ years"}.get(
        sleeve, "1-3 months"
    )


def build_research_report_v2(
    symbol: str,
    sleeve: str | None = None,
) -> dict[str, Any]:
    if AI_REPORT_SCHEMA != "v2":
        return {"error": "AI_REPORT_SCHEMA is not v2", "schema_version": AI_REPORT_SCHEMA}

    sym = symbol.upper()
    sleeve_val = sleeve or "medium"
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

    if score.recommendation:
        action = score.recommendation.recommendation
        conviction = score.recommendation.confidence
    else:
        action, conviction = _rating_from_score(score.score)

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

    report = {
        "schema_version": "2.0.0",
        "symbol": sym,
        "sleeve": sleeve_val,
        "as_of": _now_iso(),
        "final_rating": {
            "action": action,
            "conviction": conviction,
            "composite_score": score.score,
            "horizon": _horizon_for_sleeve(sleeve_val),
        },
        "executive_summary": (
            f"{sym} ({sleeve_val} sleeve) scores {score.score:.0f}/100 with {action.replace('_', ' ')} "
            f"rating. Market regime: {score.market_regime or 'neutral'}. "
            f"{score.summary[:400]}"
        ),
        "investment_thesis": {
            "bull_case": (
                score.recommendation.bull_case
                if score.recommendation
                else f"Quant composite {score.score:.0f} with top factors: "
                + ", ".join(f.display_name for f in score.factors[:3])
            ),
            "bear_case": (
                score.recommendation.bear_case
                if score.recommendation
                else ("; ".join(risk_v2.company[:3]) if not isinstance(risk_v2, dict) else score.summary)
            ),
            "edge": (
                f"Regime {score.market_regime}; data confidence "
                f"{score.recommendation.data_confidence.data_confidence:.0f}%."
                if score.recommendation and rec
                else (
                    f"Regime {score.market_regime}; data quality {rec.quality_score:.0f}%."
                    if rec
                    else "Edge from factor mix vs benchmark."
                )
            ),
        },
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
            **(score.valuation.model_dump() if score.valuation else {}),
        },
        "earnings_setup": score.earnings_setup or {},
        "similar_signal_backtest": score.similar_signal.model_dump() if score.similar_signal else None,
        "recommendation": score.recommendation.model_dump() if score.recommendation else None,
        "position_sizing": _sizing_dict(sizing_v2),
        "metadata": {
            "model_version": FACTOR_MODEL_VERSION,
            "strategy_version": STRATEGY_VERSION,
            "data_sources": ["quant_v2", "reconciled_fundamentals", "price_history"],
            "llm_model": None,
            "disclaimer": "Not investment advice. For research workflow only.",
        },
        "legacy_bucket": sleeve_val,
        "v1_score": score.score,
    }

    Cache().set(f"report_v2:{sym}:{sleeve_val}", report, REPORT_V2_CACHE_TTL)
    return report


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


def get_cached_report_v2(symbol: str, sleeve: str | None = None) -> dict | None:
    sym = symbol.upper()
    sleeve_val = sleeve or "medium"
    return Cache().get(f"report_v2:{sym}:{sleeve_val}")
