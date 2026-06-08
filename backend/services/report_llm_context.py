"""Structured quant inputs for AI report narratives — no scoring logic."""
from __future__ import annotations

from typing import Any

from models.schemas_v2 import V2ScoreResponse

# Map recommendation engine labels to report v2 final_rating.action enum
RECOMMENDATION_TO_RATING_ACTION = {
    "strong_buy": "strong_buy",
    "buy": "buy",
    "watch": "hold",
    "hold": "hold",
    "avoid": "avoid",
    "high_risk_no_decision": "avoid",
    "reduce": "reduce",
}


def _serialize(obj: Any) -> Any:
    if obj is None:
        return None
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "dict"):
        return obj.dict()
    return obj


def system_rating_from_score(score: V2ScoreResponse, *, sleeve: str) -> dict[str, Any]:
    """Authoritative system rating — never derived from LLM output."""
    horizon_map = {"penny": "3-10 days", "medium": "4-8 weeks", "compounder": "3-10+ years"}
    horizon = horizon_map.get(sleeve, "1-3 months")

    if score.recommendation:
        rec = score.recommendation
        action = RECOMMENDATION_TO_RATING_ACTION.get(rec.recommendation, "hold")
        return {
            "action": action,
            "conviction": round(float(rec.confidence), 1),
            "composite_score": round(float(score.score), 2),
            "horizon": horizon,
            "system_label": rec.recommendation,
            "gates": list(rec.gates or []),
            "time_horizon_days": rec.time_horizon_days,
            "expected_return_pct": rec.expected_return_pct,
            "expected_downside_pct": rec.expected_downside_pct,
            "source": "recommendation_engine",
        }

    return {
        "action": "hold",
        "conviction": round(min(float(score.score), 40.0), 1),
        "composite_score": round(float(score.score), 2),
        "horizon": horizon,
        "system_label": "unavailable",
        "gates": ["Quant recommendation pipeline did not produce a label."],
        "time_horizon_days": None,
        "expected_return_pct": None,
        "expected_downside_pct": None,
        "source": "score_fallback",
    }


def build_quant_report_context(
    score: V2ScoreResponse,
    *,
    sleeve: str,
    reconcile: Any | None = None,
    portfolio_symbols: list[str] | None = None,
    include_diagnostics: bool = True,
) -> dict[str, Any]:
    """
    Collect structured quant outputs for LLM explanation.

    Does not modify scores or recommendations.
    """
    sym = score.symbol
    ctx: dict[str, Any] = {
        "symbol": sym,
        "sleeve": sleeve,
        "system_rating": system_rating_from_score(score, sleeve=sleeve),
        "score_attribution": _serialize(score.attribution) or {},
        "factor_contributions": [_serialize(f) for f in score.factors],
        "risk_breakdown": {
            "risk_score": score.risk.risk_score if score.risk else None,
            "deduction_pts": score.risk.deduction_pts if score.risk else None,
            "items": score.risk.items if score.risk else [],
            "alerts": score.alerts or [],
        },
        "valuation_summary": _serialize(score.valuation) or {},
        "market_regime": score.market_regime,
        "summary": score.summary,
        "metrics": score.metrics or {},
        "data_quality": {
            "reconcile_quality_score": getattr(reconcile, "quality_score", None) if reconcile else None,
            "reconcile_flags": list(getattr(reconcile, "flags", []) or []) if reconcile else [],
            "recommendation_data_confidence": (
                _serialize(score.recommendation.data_confidence)
                if score.recommendation and score.recommendation.data_confidence
                else None
            ),
        },
        "backtest_summary": _backtest_summary(score),
        "diagnostics_summary": None,
        "factor_exposure_summary": None,
        "portfolio_impact": _serialize(score.portfolio_impact),
        "similar_signal": _serialize(score.similar_signal),
        "earnings_setup": score.earnings_setup or {},
        "position_sizing": _serialize(score.position_sizing),
    }

    if include_diagnostics:
        ctx["diagnostics_summary"] = _load_diagnostics(sym)

    if portfolio_symbols and len(portfolio_symbols) >= 2:
        ctx["factor_exposure_summary"] = _load_factor_exposure(portfolio_symbols)

    return ctx


def _backtest_summary(score: V2ScoreResponse) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if score.similar_signal:
        out["similar_signal"] = _serialize(score.similar_signal)
    if score.recommendation:
        out["expected_return_pct"] = score.recommendation.expected_return_pct
        out["expected_downside_pct"] = score.recommendation.expected_downside_pct
    return out


def _load_diagnostics(symbol: str) -> dict[str, Any] | None:
    try:
        from services.time_series_diagnostics_service import build_time_series_diagnostics

        diag = build_time_series_diagnostics(symbol, lookback=252)
        return {
            "sufficient_data": diag.get("sufficient_data"),
            "interpretation": diag.get("interpretation"),
            "annualized_volatility": diag.get("annualized_volatility"),
            "skewness": diag.get("skewness"),
            "excess_kurtosis": diag.get("excess_kurtosis"),
            "autocorrelation_lag1": (diag.get("autocorrelation") or {}).get("lag1"),
            "adf_pvalue": (diag.get("adf") or {}).get("pvalue"),
            "data_source": diag.get("data_source"),
            "notes": diag.get("notes", []),
        }
    except Exception:
        return None


def _load_factor_exposure(symbols: list[str]) -> dict[str, Any] | None:
    try:
        from services.factor_exposure_service import build_factor_exposure_report

        report = build_factor_exposure_report(symbols, benchmark="SPY", lookback_period="1y")
        return {
            "benchmark": report.get("benchmark"),
            "symbols_used": report.get("symbols_used"),
            "observation_count": report.get("observation_count"),
            "concentration_warning": report.get("concentration_warning"),
            "pca_pc1_variance_ratio": (report.get("pca") or {}).get("pc1_variance_ratio"),
            "notes": report.get("notes", [])[:3],
        }
    except Exception:
        return None
