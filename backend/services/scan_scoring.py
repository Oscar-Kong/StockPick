"""Stage B scan scoring — legacy screener path with optional ScoringEngine routing."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from config import PERSIST_SCORE_ATTRIBUTION, USE_SCORING_ENGINE_IN_SCAN
from engines.scoring.engine import ScoringEngine, ScoringResult
from models.schemas import Bucket, RiskLevel
from scoring.data_quality import adjust_score_for_data_quality
from screeners.base import BaseScreener, CandidateContext, WeightedSignal
from services.market_context import enrich_metrics
from services.scan_parity import StageBParityRecord, build_stage_b_parity_record, log_stage_b_parity

logger = logging.getLogger(__name__)


@dataclass
class ScanScoreOutcome:
    """Normalized Stage B score payload for StockResult assembly."""

    score: float
    signals: list[WeightedSignal]
    risk: RiskLevel
    summary: str
    metrics: dict[str, Any]
    raw_score: float
    legacy_score: float
    parity_delta: float | None = None
    scoring_engine_used: bool = False
    parity_record: StageBParityRecord | None = None


def _apply_openbb_adjustment(score: float, metrics: dict[str, Any]) -> float:
    try:
        from services.openbb_integration import apply_openbb_score_adjustment

        return apply_openbb_score_adjustment(score, metrics)
    except Exception:
        return score


def _build_legacy_outcome(
    *,
    ctx: CandidateContext,
    legacy_score: float,
    signals: list[WeightedSignal],
    risk: RiskLevel,
    summary: str,
    legacy_metrics: dict[str, Any],
    bucket: Bucket,
    symbol: str,
    quality_score: float | None,
    strategy_version: str,
    quality_filter: dict[str, Any],
) -> ScanScoreOutcome:
    """Apply post-screener adjustments for the legacy scan path."""
    raw_score = legacy_score
    score = adjust_score_for_data_quality(legacy_score, quality_score)
    metrics = enrich_metrics(
        symbol,
        ctx.info,
        ctx.fundamentals,
        dict(legacy_metrics),
        bucket,
        allow_openbb_fetch=False,
    )
    score = _apply_openbb_adjustment(score, metrics)
    metrics["strategy_version"] = strategy_version
    metrics["quality_filter"] = quality_filter
    metrics["data_quality_score"] = quality_score
    metrics["raw_score"] = round(raw_score, 1)
    metrics["score_adjusted_for_data_quality"] = score != raw_score

    return ScanScoreOutcome(
        score=round(score, 1),
        signals=signals,
        risk=risk,
        summary=summary,
        metrics=metrics,
        raw_score=raw_score,
        legacy_score=round(score, 1),
        parity_delta=None,
        scoring_engine_used=False,
    )


def _persist_engine_attribution(scoring: ScoringResult, *, symbol: str, sleeve: str) -> None:
    if not PERSIST_SCORE_ATTRIBUTION:
        return
    try:
        from engines.store import persist_score_attribution

        factor_dicts = [
            {
                "factor_id": f.factor_id,
                "display_name": f.display_name,
                "norm_score": f.norm_score,
                "weight": f.weight,
                "contribution": f.contribution,
                "description": f.description,
            }
            for f in scoring.factors
        ]
        weights = {f.factor_id: f.weight for f in scoring.factors}
        persist_score_attribution(
            symbol=symbol,
            sleeve=sleeve,
            raw_score=scoring.raw_score,
            dq_multiplier=scoring.dq_multiplier,
            risk_deduction=0.0,
            regime_mult=scoring.regime_mult,
            sector_tilt=scoring.sector_tilt,
            final_score=scoring.final_score,
            factors=factor_dicts,
            weights=weights,
        )
    except Exception as exc:
        logger.warning("Failed to persist scan score attribution for %s: %s", symbol, exc)


def log_score_parity(
    *,
    symbol: str,
    sleeve: str,
    legacy_score: float,
    engine_score: float,
    factors: list[Any] | None = None,
) -> StageBParityRecord:
    """Build structured parity record and log legacy vs ScoringEngine delta."""
    record = build_stage_b_parity_record(
        symbol=symbol,
        sleeve=sleeve,
        legacy_score=legacy_score,
        engine_score=engine_score,
        factors=factors or [],
        scoring_engine_used=True,
    )
    log_stage_b_parity(record)
    return record


def score_stage_b_candidate(
    *,
    ctx: CandidateContext,
    screener: BaseScreener,
    bucket: Bucket,
    symbol: str,
    quality_score: float | None,
    strategy_version: str,
    quality_filter: dict[str, Any],
) -> ScanScoreOutcome:
    """Score one Stage B candidate; route through ScoringEngine when flag enabled."""
    sleeve = bucket.value

    legacy_score, legacy_signals, legacy_risk, legacy_summary, legacy_metrics = screener.score(ctx)
    legacy_raw = legacy_score
    legacy_after_dq = adjust_score_for_data_quality(legacy_score, quality_score)
    legacy_metrics_work = enrich_metrics(
        symbol,
        ctx.info,
        ctx.fundamentals,
        dict(legacy_metrics),
        bucket,
        allow_openbb_fetch=False,
    )
    legacy_final = round(_apply_openbb_adjustment(legacy_after_dq, legacy_metrics_work), 1)

    if not USE_SCORING_ENGINE_IN_SCAN:
        return _build_legacy_outcome(
            ctx=ctx,
            legacy_score=legacy_score,
            signals=legacy_signals,
            risk=legacy_risk,
            summary=legacy_summary,
            legacy_metrics=legacy_metrics,
            bucket=bucket,
            symbol=symbol,
            quality_score=quality_score,
            strategy_version=strategy_version,
            quality_filter=quality_filter,
        )

    metrics = enrich_metrics(
        symbol,
        ctx.info,
        ctx.fundamentals,
        dict(legacy_metrics),
        bucket,
        allow_openbb_fetch=False,
    )
    scoring = ScoringEngine.score(
        ctx,
        sleeve,
        quality_score=quality_score,
        apply_openbb=True,
        metrics=metrics,
    )
    parity_record = log_score_parity(
        symbol=symbol,
        sleeve=sleeve,
        legacy_score=legacy_final,
        engine_score=scoring.final_score,
        factors=scoring.factors,
    )
    _persist_engine_attribution(scoring, symbol=symbol, sleeve=sleeve)

    merged_metrics = {**legacy_metrics, **scoring.metrics}
    merged_metrics["strategy_version"] = strategy_version
    merged_metrics["quality_filter"] = quality_filter
    merged_metrics["data_quality_score"] = quality_score
    merged_metrics["raw_score"] = round(scoring.raw_score, 1)
    merged_metrics["legacy_raw_score"] = round(legacy_raw, 1)
    merged_metrics["legacy_score"] = legacy_final
    merged_metrics["score_adjusted_for_data_quality"] = scoring.final_score != scoring.raw_score
    merged_metrics["scoring_engine"] = True
    merged_metrics["parity_delta"] = parity_record.parity_delta
    merged_metrics["parity"] = parity_record.to_dict()
    merged_metrics["scoring_engine_attribution"] = {
        "regime_mult": scoring.regime_mult,
        "sector_tilt": scoring.sector_tilt,
        "dq_multiplier": scoring.dq_multiplier,
        "openbb_delta": scoring.openbb_delta,
        "score_after_regime": scoring.score_after_regime,
        "score_after_dq": scoring.score_after_dq,
        "score_after_openbb": scoring.score_after_openbb,
    }

    return ScanScoreOutcome(
        score=round(scoring.final_score, 1),
        signals=scoring.signals,
        risk=scoring.risk_level,
        summary=scoring.summary,
        metrics=merged_metrics,
        raw_score=scoring.raw_score,
        legacy_score=legacy_final,
        parity_delta=parity_record.parity_delta,
        scoring_engine_used=True,
        parity_record=parity_record,
    )
