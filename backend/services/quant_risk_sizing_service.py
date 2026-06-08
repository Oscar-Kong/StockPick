"""Orchestrate unified risk + position sizing for v2 API."""
from __future__ import annotations

from typing import Any

from config import DEFAULT_ACTIVE_POSITIONS, DEFAULT_PORTFOLIO_EXPOSURE, POSITION_SIZING_V2, RISK_ENGINE_V2
from data.price_service import PriceService
from data.reconciler import DataReconciler
from engines.risk.unified import UnifiedRiskEngine
from engines.sizing.engine import PositionSizingEngine
from engines.store import persist_position_recommendation
from models.schemas_v2 import PositionSizingV2, UnifiedRiskV2, VolatilityRiskV2, V2ScoreResponse
from quant_core.returns import simple_returns


def sizing_from_score_context(
    symbol: str,
    sleeve: str,
    *,
    final_score: float,
    data_quality_score: float | None,
    risk_index: float,
    portfolio_exposure: float | None = None,
    active_positions: int | None = None,
    persist: bool = True,
) -> PositionSizingV2 | None:
    """Compute sizing from precomputed score inputs (no build_v2_score call)."""
    if not POSITION_SIZING_V2:
        return None

    sym = symbol.upper()
    ps = PriceService()
    hist = ps.get_history(sym, period="1y")
    sizing = PositionSizingEngine.compute(
        sleeve=sleeve,
        final_score=final_score,
        data_quality_score=data_quality_score,
        risk_index=risk_index,
        portfolio_exposure=portfolio_exposure if portfolio_exposure is not None else DEFAULT_PORTFOLIO_EXPOSURE,
        active_positions=active_positions if active_positions is not None else DEFAULT_ACTIVE_POSITIONS,
        history=hist,
    )
    if sizing is None:
        return None

    if persist:
        try:
            persist_position_recommendation(
                symbol=sym,
                sleeve=sleeve,
                recommended_pct=sizing.recommended_pct,
                max_pct=sizing.max_pct,
                stop_loss_pct=sizing.stop_loss_pct,
                portfolio_alloc_pct=sizing.portfolio_allocation_pct,
                inputs=sizing.inputs,
            )
        except Exception:
            pass

    return PositionSizingV2(
        symbol=sym,
        sleeve=sleeve,
        recommended_weight_pct=sizing.recommended_pct,
        max_weight_pct=sizing.max_pct,
        stop_loss_pct=sizing.stop_loss_pct,
        portfolio_allocation_pct=sizing.portfolio_allocation_pct,
        conviction=sizing.conviction,
        sleeve_max_pct=sizing.sleeve_max_pct,
        risk_multiplier=sizing.risk_multiplier,
        dq_multiplier=sizing.dq_multiplier,
        rationale=sizing.rationale,
    )


def build_unified_risk(
    symbol: str,
    sleeve: str,
    *,
    portfolio_exposure: float | None = None,
    score_result: V2ScoreResponse | dict[str, Any] | None = None,
) -> UnifiedRiskV2 | dict[str, Any]:
    if score_result is None:
        from services.quant_v2_service import build_v2_score

        score_result = build_v2_score(
            symbol,
            sleeve,
            validate_parity=False,
            include_sizing=False,
            persist_snapshot=False,
        )
    if isinstance(score_result, dict) and score_result.get("error"):
        return score_result

    rec = DataReconciler().reconcile(symbol.upper())
    metrics = score_result.metrics or {}
    hist = PriceService().get_history(symbol.upper(), period="1y")
    rets = simple_returns(hist["close"]) if not hist.empty and "close" in hist.columns else None
    risk = UnifiedRiskEngine.assess(
        symbol.upper(),
        sleeve,
        final_score=score_result.score,
        days_until_earnings=metrics.get("days_until_earnings"),
        valuation_warnings=metrics.get("valuation_warnings"),
        data_quality_score=rec.quality_score if rec else None,
        reconcile_flags=rec.flags if rec else [],
        openbb_risk_flags=metrics.get("openbb_risk_flags"),
        openbb_governance_score=metrics.get("openbb_governance_score"),
        metrics=metrics,
        returns=rets if RISK_ENGINE_V2 else None,
    )

    vol_payload = risk.volatility_risk or {}
    volatility = VolatilityRiskV2(**vol_payload) if vol_payload else None

    return UnifiedRiskV2(
        symbol=symbol.upper(),
        sleeve=sleeve,
        risk_index=risk.risk_index,
        safety_score=risk.safety_score,
        deduction_pts=risk.deduction_pts,
        macro=risk.macro,
        company=risk.company,
        events=risk.events,
        score_deductions=risk.score_deductions,
        alerts=risk.alerts,
        breakdown=risk.breakdown,
        volatility=volatility,
    )


def build_position_sizing(
    symbol: str,
    sleeve: str,
    *,
    portfolio_exposure: float | None = None,
    active_positions: int | None = None,
    persist: bool = True,
    score_result: V2ScoreResponse | dict[str, Any] | None = None,
) -> PositionSizingV2 | dict[str, Any] | None:
    if not POSITION_SIZING_V2:
        return None

    if score_result is None:
        from services.quant_v2_service import build_v2_score

        score_result = build_v2_score(
            symbol,
            sleeve,
            validate_parity=False,
            include_sizing=False,
            persist_snapshot=False,
        )
    if isinstance(score_result, dict) and score_result.get("error"):
        return score_result

    rec = DataReconciler().reconcile(symbol.upper())
    risk_index = score_result.risk.risk_score if score_result.risk else 50.0
    return sizing_from_score_context(
        symbol,
        sleeve,
        final_score=score_result.score,
        data_quality_score=rec.quality_score if rec else None,
        risk_index=risk_index,
        portfolio_exposure=portfolio_exposure,
        active_positions=active_positions,
        persist=persist,
    )
