"""Orchestrate quant v2 score pipeline."""
from __future__ import annotations

import logging
from typing import Any

from buckets import DEFAULT_BUCKET
from config import (
    DYNAMIC_WEIGHTS_ENABLED,
    FACTOR_MODEL_VERSION,
    MULTI_AGENT_PIPELINE_ENABLED,
    PERSIST_SCORE_ATTRIBUTION,
    POSITION_SIZING_V2,
    PREDICTION_SNAPSHOTS_ENABLED,
    RISK_ENGINE_V2,
    RISK_ENGINE_V2,
    SCORE_ENGINE_V2_ENABLED,
    STRATEGY_VERSION,
    VALUATION_ENGINE_ENABLED,
)
from models.schemas_v2 import (
    DataConfidenceV2,
    FactorContributionV2,
    PillarScoresV2,
    PortfolioImpactV2,
    PositionSizingV2,
    RecommendationV2,
    RiskBreakdownV2,
    ScoreAttributionV2,
    SimilarSignalV2,
    ValuationV2,
    V2ScoreResponse,
)
from data.reconciler import DataReconciler
from engines.risk.engine import RiskEngine
from engines.scoring.engine import ScoringEngine
from engines.scoring.liquidity import liquidity_penalty
from engines.store import persist_risk_score, persist_score_attribution
from models.schemas import Bucket
from screeners.compounder import CompounderScreener
from screeners.medium import MediumScreener
from screeners.penny import PennyScreener
from services.market_context import enrich_metrics
from services.watchlist_scanner import analyze_symbol
from quant_core.returns import simple_returns
from utils.pydantic_util import model_to_dict

logger = logging.getLogger(__name__)

_SCREENERS = {
    "penny": PennyScreener,
    "medium": MediumScreener,
    "compounder": CompounderScreener,
}


def build_v2_score(
    symbol: str,
    sleeve: str | None = None,
    *,
    validate_parity: bool = True,
    persist_snapshot: bool = True,
    include_sizing: bool = True,
) -> V2ScoreResponse | dict[str, Any]:
    if not SCORE_ENGINE_V2_ENABLED:
        return {"error": "SCORE_ENGINE_V2_ENABLED is false"}

    sym = symbol.upper()
    sleeve = sleeve or DEFAULT_BUCKET
    if sleeve not in _SCREENERS:
        return {"error": f"Invalid sleeve: {sleeve}"}

    screener = _SCREENERS[sleeve]()
    ctx = screener.enrich(sym)
    if ctx is None:
        return {"error": f"Could not load data for {sym}"}

    rec = DataReconciler().reconcile(sym)
    quality = rec.quality_score if rec else ctx.info.get("_reconcile_quality")
    try:
        from data.pit_fundamentals import persist_reconcile_as_pit

        if rec and rec.canonical:
            persist_reconcile_as_pit(sym, rec.canonical)
    except Exception:
        pass

    metrics: dict[str, Any] = {}
    metrics = enrich_metrics(
        sym,
        ctx.info,
        ctx.fundamentals,
        metrics,
        Bucket(sleeve),
        allow_openbb_fetch=False,
    )

    scoring = ScoringEngine.score(
        ctx,
        sleeve,
        quality_score=quality,
        apply_openbb=True,
        metrics=metrics,
    )

    rets = None
    if RISK_ENGINE_V2 and ctx.history is not None and not getattr(ctx.history, "empty", True):
        if "close" in ctx.history.columns:
            rets = simple_returns(ctx.history["close"])

    risk_assess = RiskEngine.assess(
        sym,
        sleeve,
        final_score=scoring.final_score,
        days_until_earnings=metrics.get("days_until_earnings"),
        valuation_warnings=metrics.get("valuation_warnings"),
        data_quality_score=quality,
        reconcile_flags=rec.flags if rec else [],
        last_scanned_at=None,
        openbb_risk_flags=metrics.get("openbb_risk_flags"),
        openbb_governance_score=metrics.get("openbb_governance_score"),
        apply_deduction=RISK_ENGINE_V2,
        returns=rets,
    )

    final = RiskEngine.apply_deduction(scoring.final_score, risk_assess)

    liq_pen, liq_note = liquidity_penalty(ctx.info, price=ctx.price)
    metrics["liquidity_penalty"] = liq_pen
    metrics["liquidity_note"] = liq_note

    valuation_payload: ValuationV2 | None = None
    earnings_dict: dict[str, Any] = {}
    if VALUATION_ENGINE_ENABLED:
        try:
            from engines.valuation.engine import evaluate_valuation
            from engines.earnings.revisions import build_earnings_setup

            val = evaluate_valuation(ctx.info, ctx.fundamentals, symbol=sym)
            valuation_payload = ValuationV2(**val.to_dict())
            earnings = build_earnings_setup(
                sym,
                ctx.info,
                ctx.fundamentals,
                days_until_earnings=metrics.get("days_until_earnings"),
                valuation_verdict=val.verdict,
            )
            earnings_dict = earnings.to_dict()
        except Exception as exc:
            logger.debug("Valuation/earnings setup skipped for %s: %s", sym, exc)

    parity_delta: float | None = None
    if validate_parity:
        try:
            bucket = Bucket(sleeve)
            legacy, err = analyze_symbol(sym, bucket)
            if legacy and not err:
                parity_delta = round(abs(legacy.score - final), 2)
        except Exception as exc:
            logger.debug("Parity check skipped for %s: %s", sym, exc)

    factors = [
        FactorContributionV2(
            factor_id=f.factor_id,
            display_name=f.display_name,
            norm_score=f.norm_score,
            weight=f.weight,
            contribution=f.contribution,
            description=f.description,
        )
        for f in scoring.factors
    ]
    factor_dicts = [model_to_dict(f) for f in factors]

    weights = {f.factor_id: f.weight for f in scoring.factors}
    attribution = ScoreAttributionV2(
        raw_score=scoring.raw_score,
        regime_mult=scoring.regime_mult,
        sector_tilt=scoring.sector_tilt,
        dq_multiplier=scoring.dq_multiplier,
        openbb_delta=scoring.openbb_delta,
        score_after_regime=scoring.score_after_regime,
        score_after_dq=scoring.score_after_dq,
        risk_deduction=risk_assess.deduction_pts,
        final_score=final,
    )

    if PERSIST_SCORE_ATTRIBUTION:
        try:
            persist_score_attribution(
                symbol=sym,
                sleeve=sleeve,
                raw_score=scoring.raw_score,
                dq_multiplier=scoring.dq_multiplier,
                risk_deduction=risk_assess.deduction_pts,
                regime_mult=scoring.regime_mult,
                sector_tilt=scoring.sector_tilt,
                final_score=final,
                factors=factor_dicts,
                weights=weights,
            )
            persist_risk_score(
                symbol=sym,
                sleeve=sleeve,
                risk_score=risk_assess.risk_score,
                deduction_pts=risk_assess.deduction_pts,
                breakdown=risk_assess.breakdown,
            )
        except Exception as exc:
            logger.warning("Failed to persist v2 attribution for %s: %s", sym, exc)

    regime_name = None
    try:
        from engines.weighting.weight_store import WeightStore

        regime_name = WeightStore.current_regime()
    except Exception:
        pass

    similar_payload: SimilarSignalV2 | None = None
    try:
        from engines.backtest.similar_signal import run_similar_signal_backtest

        sim = run_similar_signal_backtest(
            symbol=sym,
            sleeve=sleeve,
            current_factors=factor_dicts,
            market_regime=regime_name,
        )
        if sim.get("sample_n", 0) > 0:
            similar_payload = SimilarSignalV2(
                sample_n=sim["sample_n"],
                avg_forward_return_pct=sim.get("avg_forward_return_pct"),
                win_rate=sim.get("win_rate"),
                max_drawdown_pct=sim.get("max_drawdown_pct"),
                forward_days=sim.get("forward_days", 60),
            )
    except Exception as exc:
        logger.debug("Similar signal backtest skipped: %s", exc)

    sizing_payload: PositionSizingV2 | None = None
    portfolio_impact_payload: PortfolioImpactV2 | None = None
    if POSITION_SIZING_V2 and include_sizing:
        try:
            from services.portfolio_impact import estimate_portfolio_impact
            from services.quant_risk_sizing_service import sizing_from_score_context

            s = sizing_from_score_context(
                sym,
                sleeve,
                final_score=final,
                data_quality_score=quality,
                risk_index=risk_assess.risk_score,
                persist=PERSIST_SCORE_ATTRIBUTION,
            )
            if s:
                sizing_payload = s
                impact = estimate_portfolio_impact(
                    sym,
                    sector=ctx.info.get("sector"),
                    recommended_weight_pct=s.recommended_weight_pct,
                )
                portfolio_impact_payload = PortfolioImpactV2(**impact)
        except Exception:
            pass

    recommendation_payload: RecommendationV2 | None = None
    agents_payload: dict[str, Any] | None = None
    snapshot_id: int | None = None
    try:
        from engines.recommendation.engine import recommendation_from_context

        rec_obj = recommendation_from_context(
            sym,
            sleeve,
            final,
            factor_dicts,
            risk_assess,
            ctx.info,
            reconcile=rec,
            valuation=valuation_payload,
            catalyst_score=earnings_dict.get("catalyst_score") if earnings_dict else None,
            liquidity_penalty=liq_pen,
            similar_signal=model_to_dict(similar_payload) if similar_payload else None,
            portfolio_impact=model_to_dict(portfolio_impact_payload) if portfolio_impact_payload else None,
            summary=scoring.summary,
        )
        p = rec_obj.pillars.to_dict()
        dc = rec_obj.data_confidence.to_dict()
        recommendation_payload = RecommendationV2(
            recommendation=rec_obj.label,
            confidence=rec_obj.confidence,
            time_horizon_days=rec_obj.time_horizon_days,
            expected_return_pct=rec_obj.expected_return_pct,
            expected_downside_pct=rec_obj.expected_downside_pct,
            pillars=PillarScoresV2(**p),
            data_confidence=DataConfidenceV2(**dc),
            gates=rec_obj.gates,
            bull_case=rec_obj.bull_case,
            bear_case=rec_obj.bear_case,
        )

        if MULTI_AGENT_PIPELINE_ENABLED:
            from services.agent_orchestrator import run_agent_pipeline

            agents_payload = run_agent_pipeline(
                symbol=sym,
                info=ctx.info,
                fundamentals=ctx.fundamentals,
                factors=factor_dicts,
                risk_assess=risk_assess,
                recommendation=model_to_dict(recommendation_payload),
                rec=rec,
                days_until_earnings=metrics.get("days_until_earnings"),
                similar_signal=model_to_dict(similar_payload) if similar_payload else None,
            )

        if PREDICTION_SNAPSHOTS_ENABLED and persist_snapshot:
            from engines.prediction.snapshots import persist_prediction_snapshot
            from services.feature_provenance import features_from_reconcile, persist_feature_provenance

            try:
                persist_feature_provenance(sym, features_from_reconcile(rec))
            except Exception:
                pass

            snapshot_id = persist_prediction_snapshot(
                symbol=sym,
                sleeve=sleeve,
                price=ctx.price,
                recommendation=rec_obj.label,
                confidence=rec_obj.confidence,
                time_horizon_days=rec_obj.time_horizon_days,
                alpha_score=rec_obj.pillars.alpha_score,
                valuation_score=rec_obj.pillars.valuation_score,
                catalyst_score=rec_obj.pillars.catalyst_score,
                risk_score=risk_assess.risk_score,
                data_confidence=rec_obj.data_confidence.score,
                market_regime=regime_name,
                expected_return_pct=rec_obj.expected_return_pct,
                expected_downside_pct=rec_obj.expected_downside_pct,
                features={
                    "factors": factor_dicts,
                    "sector": ctx.info.get("sector"),
                    "liquidity_penalty": liq_pen,
                },
                thesis={"bull_case": rec_obj.bull_case, "bear_case": rec_obj.bear_case},
            )
    except Exception as exc:
        logger.warning("Recommendation pipeline failed for %s: %s", sym, exc)

    try:
        from data.historical_store import HistoricalStore

        HistoricalStore().save_factor_snapshot(
            sym,
            sleeve,
            STRATEGY_VERSION,
            {f["factor_id"]: f["norm_score"] for f in factor_dicts},
            score=final,
        )
    except Exception:
        pass

    return V2ScoreResponse(
        symbol=sym,
        sleeve=sleeve,
        score=final,
        market_regime=regime_name,
        dynamic_weights=bool(DYNAMIC_WEIGHTS_ENABLED),
        position_sizing=sizing_payload,
        recommendation=recommendation_payload,
        valuation=valuation_payload,
        earnings_setup=earnings_dict,
        similar_signal=similar_payload,
        portfolio_impact=portfolio_impact_payload,
        prediction_snapshot_id=snapshot_id,
        agents=agents_payload,
        risk_level=scoring.risk_level.value,
        summary=scoring.summary,
        factors=factors,
        attribution=attribution,
        risk=RiskBreakdownV2(
            risk_score=risk_assess.risk_score,
            deduction_pts=risk_assess.deduction_pts,
            items=risk_assess.breakdown,
        ),
        alerts=risk_assess.alerts,
        strategy_version=STRATEGY_VERSION,
        factor_model_version=FACTOR_MODEL_VERSION,
        parity_delta=parity_delta,
        metrics=scoring.metrics,
    )


def maybe_persist_from_analysis(
    symbol: str,
    bucket: str,
    *,
    score: float,
    signals: list[dict],
    metrics: dict,
    data_quality_score: float | None,
    reconcile_flags: list[str] | None,
) -> None:
    """Lightweight attribution persist from v1 analyze path (no full v2 recompute)."""
    if not PERSIST_SCORE_ATTRIBUTION:
        return
    try:
        raw = float(metrics.get("raw_score") or score)
        regime = metrics.get("regime") or {}
        regime_mult = float(regime.get("final_multiplier") or 1.0)
        sector_tilt = float((regime.get("sector_regime") or {}).get("tilt") or 0.0)
        from engines.scoring.data_quality import dq_multiplier

        mult = dq_multiplier(data_quality_score)
        factors = []
        weights: dict[str, float] = {}
        from engines.factor.catalog import signal_name_to_factor_id

        for s in signals:
            name = s.get("name", "")
            fid = signal_name_to_factor_id(bucket, name)
            w = float(s.get("weight") or 0)
            weights[fid] = w
            factors.append(
                {
                    "factor_id": fid,
                    "display_name": name,
                    "norm_score": s.get("value"),
                    "weight": w,
                    "contribution": s.get("contribution"),
                }
            )
        persist_score_attribution(
            symbol=symbol,
            sleeve=bucket,
            raw_score=raw,
            dq_multiplier=mult,
            risk_deduction=0.0,
            regime_mult=regime_mult,
            sector_tilt=sector_tilt,
            final_score=score,
            factors=factors,
            weights=weights,
        )
    except Exception as exc:
        logger.debug("Analyze attribution persist skipped: %s", exc)
