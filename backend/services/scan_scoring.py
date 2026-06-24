"""Stage B scan scoring — mode-aware legacy / ScoringEngine routing."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from config import FACTOR_MODEL_VERSION, PERSIST_SCORE_ATTRIBUTION
from engines.scoring.engine import ScoringEngine, ScoringResult
from models.schemas import Bucket, RiskLevel
from scoring.data_quality import adjust_score_for_data_quality
from screeners.base import BaseScreener, CandidateContext, WeightedSignal
from services.market_context import enrich_metrics
from services.scan_parity import StageBParityRecord, build_stage_b_parity_record, log_stage_b_parity
from services.scan_scoring_config import (
    ScanScoringMode,
    legacy_parity_comparison_enabled,
    primary_scorer_is_engine,
    resolve_scan_scoring_mode,
)

logger = logging.getLogger(__name__)


@dataclass
class CandidateFeatures:
    """Shared Stage B inputs — enrich once, consume from both scorers in parity mode."""

    symbol: str
    bucket: Bucket
    ctx: CandidateContext
    enriched_metrics: dict[str, Any]
    base_display_metrics: dict[str, Any] = field(default_factory=dict)
    quality_score: float | None = None


@dataclass
class ScanScoreOutcome:
    """Normalized Stage B score payload for StockResult assembly."""

    score: float
    signals: list[WeightedSignal]
    risk: RiskLevel
    summary: str
    metrics: dict[str, Any]
    raw_score: float
    legacy_score: float | None = None
    parity_delta: float | None = None
    scoring_engine_used: bool = False
    parity_record: StageBParityRecord | None = None
    scoring_mode: str = "legacy"
    legacy_invoked: bool = False
    engine_invoked: bool = False
    parity_sampled: bool = False
    timings_ms: dict[str, float] = field(default_factory=dict)


def _apply_openbb_adjustment(score: float, metrics: dict[str, Any]) -> float:
    try:
        from services.openbb_integration import apply_openbb_score_adjustment

        return apply_openbb_score_adjustment(score, metrics)
    except Exception:
        return score


def _base_display_metrics(ctx: CandidateContext, bucket: Bucket) -> dict[str, Any]:
    """Bucket-specific display metrics without running full legacy score()."""
    df = ctx.history
    metrics: dict[str, Any] = {"sector": ctx.info.get("sector")}
    if bucket == Bucket.penny and df is not None and not df.empty:
        from scoring.penny_liquidity import compute_penny_liquidity_metrics
        from scoring.technical import momentum_score

        metrics.update(compute_penny_liquidity_metrics(df).to_metrics_dict())
        metrics["momentum_5d"] = momentum_score(df, 5)
        metrics["hold_horizon"] = "3-10 days"
    elif bucket == Bucket.compounder:
        metrics["hold_horizon"] = "multi-year"
    return metrics


def prepare_candidate_features(
    *,
    ctx: CandidateContext,
    bucket: Bucket,
    symbol: str,
    quality_score: float | None,
) -> CandidateFeatures:
    """Single enrichment pass shared by engine and parity legacy comparison."""
    base = _base_display_metrics(ctx, bucket)
    enriched = enrich_metrics(
        symbol,
        ctx.info,
        ctx.fundamentals,
        dict(base),
        bucket,
        allow_openbb_fetch=False,
    )
    return CandidateFeatures(
        symbol=symbol.upper(),
        bucket=bucket,
        ctx=ctx,
        enriched_metrics=enriched,
        base_display_metrics=base,
        quality_score=quality_score,
    )


def _finalize_legacy_metrics(
    metrics: dict[str, Any],
    *,
    strategy_version: str,
    quality_filter: dict[str, Any],
    quality_score: float | None,
    raw_score: float,
    score: float,
) -> dict[str, Any]:
    out = dict(metrics)
    out["strategy_version"] = strategy_version
    out["quality_filter"] = quality_filter
    out["data_quality_score"] = quality_score
    out["raw_score"] = round(raw_score, 1)
    out["score_adjusted_for_data_quality"] = score != raw_score
    return out


def _build_legacy_outcome(
    *,
    features: CandidateFeatures,
    legacy_score: float,
    signals: list[WeightedSignal],
    risk: RiskLevel,
    summary: str,
    legacy_metrics: dict[str, Any],
    strategy_version: str,
    quality_filter: dict[str, Any],
    scoring_mode: ScanScoringMode,
    timings_ms: dict[str, float],
) -> ScanScoreOutcome:
    raw_score = legacy_score
    score = adjust_score_for_data_quality(legacy_score, features.quality_score)
    merged = {**features.enriched_metrics, **legacy_metrics}
    score = _apply_openbb_adjustment(score, merged)
    metrics = _finalize_legacy_metrics(
        merged,
        strategy_version=strategy_version,
        quality_filter=quality_filter,
        quality_score=features.quality_score,
        raw_score=raw_score,
        score=score,
    )
    metrics["scoring_mode"] = scoring_mode

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
        scoring_mode=scoring_mode,
        legacy_invoked=True,
        engine_invoked=False,
        timings_ms=timings_ms,
    )


def _build_engine_outcome(
    *,
    features: CandidateFeatures,
    scoring: ScoringResult,
    strategy_version: str,
    quality_filter: dict[str, Any],
    scoring_mode: ScanScoringMode,
    legacy_score: float | None = None,
    parity_record: StageBParityRecord | None = None,
    extra_metrics: dict[str, Any] | None = None,
    timings_ms: dict[str, float],
) -> ScanScoreOutcome:
    merged_metrics = {**features.enriched_metrics, **(extra_metrics or {}), **scoring.metrics}
    merged_metrics["strategy_version"] = strategy_version
    merged_metrics["quality_filter"] = quality_filter
    merged_metrics["data_quality_score"] = features.quality_score
    merged_metrics["raw_score"] = round(scoring.raw_score, 1)
    merged_metrics["score_adjusted_for_data_quality"] = scoring.final_score != scoring.raw_score
    merged_metrics["scoring_engine"] = True
    merged_metrics["scoring_mode"] = scoring_mode
    merged_metrics["scoring_engine_attribution"] = {
        "regime_mult": scoring.regime_mult,
        "sector_tilt": scoring.sector_tilt,
        "dq_multiplier": scoring.dq_multiplier,
        "openbb_delta": scoring.openbb_delta,
        "score_after_regime": scoring.score_after_regime,
        "score_after_dq": scoring.score_after_dq,
        "score_after_openbb": scoring.score_after_openbb,
    }
    if legacy_score is not None:
        merged_metrics["legacy_score"] = legacy_score
    if parity_record is not None:
        merged_metrics["parity_delta"] = parity_record.parity_delta
        merged_metrics["parity"] = parity_record.to_dict()

    return ScanScoreOutcome(
        score=round(scoring.final_score, 1),
        signals=scoring.signals,
        risk=scoring.risk_level,
        summary=scoring.summary,
        metrics=merged_metrics,
        raw_score=scoring.raw_score,
        legacy_score=legacy_score,
        parity_delta=parity_record.parity_delta if parity_record else None,
        scoring_engine_used=True,
        parity_record=parity_record,
        scoring_mode=scoring_mode,
        legacy_invoked=legacy_score is not None,
        engine_invoked=True,
        parity_sampled=parity_record is not None,
        timings_ms=timings_ms,
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
    legacy_signals: list[WeightedSignal] | None = None,
    scan_id: str = "",
    scoring_version: str | None = None,
) -> StageBParityRecord:
    """Build structured parity record and log legacy vs ScoringEngine delta."""
    record = build_stage_b_parity_record(
        symbol=symbol,
        sleeve=sleeve,
        legacy_score=legacy_score,
        engine_score=engine_score,
        factors=factors or [],
        legacy_signals=legacy_signals,
        scoring_engine_used=True,
        scan_id=scan_id,
        scoring_version=scoring_version or FACTOR_MODEL_VERSION,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
    log_stage_b_parity(record)
    return record


def _run_legacy_score(
    screener: BaseScreener,
    ctx: CandidateContext,
) -> tuple[float, list[WeightedSignal], RiskLevel, str, dict[str, Any], float]:
    """Execute legacy screener.score() and return raw tuple plus adjusted final."""
    legacy_score, signals, risk, summary, legacy_metrics = screener.score(ctx)
    legacy_after_dq = adjust_score_for_data_quality(legacy_score, ctx.info.get("_reconcile_quality"))
    return legacy_score, signals, risk, summary, legacy_metrics, legacy_after_dq


def score_stage_b_candidate(
    *,
    ctx: CandidateContext,
    screener: BaseScreener,
    bucket: Bucket,
    symbol: str,
    quality_score: float | None,
    strategy_version: str,
    quality_filter: dict[str, Any],
    scan_id: str = "",
    scoring_mode: ScanScoringMode | None = None,
) -> ScanScoreOutcome:
    """Score one Stage B candidate using configured scoring mode."""
    mode = scoring_mode or resolve_scan_scoring_mode()
    sleeve = bucket.value
    timings_ms: dict[str, float] = {}
    run_legacy = legacy_parity_comparison_enabled(mode, scan_id, symbol)
    run_engine = primary_scorer_is_engine(mode)

    prep_started = time.monotonic()
    features = prepare_candidate_features(
        ctx=ctx,
        bucket=bucket,
        symbol=symbol,
        quality_score=quality_score,
    )
    timings_ms["enrich_ms"] = round((time.monotonic() - prep_started) * 1000.0, 2)

    legacy_final: float | None = None
    legacy_signals: list[WeightedSignal] | None = None
    legacy_metrics_extra: dict[str, Any] = {}
    legacy_summary = ""
    legacy_risk = RiskLevel.medium
    legacy_raw = 0.0

    if run_legacy:
        legacy_started = time.monotonic()
        legacy_raw, legacy_signals, legacy_risk, legacy_summary, legacy_metrics_extra, legacy_after_dq = (
            _run_legacy_score(screener, ctx)
        )
        legacy_work = {**features.enriched_metrics, **legacy_metrics_extra}
        legacy_final = round(_apply_openbb_adjustment(legacy_after_dq, legacy_work), 1)
        timings_ms["legacy_ms"] = round((time.monotonic() - legacy_started) * 1000.0, 2)

    if mode == "legacy":
        assert legacy_signals is not None
        return _build_legacy_outcome(
            features=features,
            legacy_score=legacy_raw,
            signals=legacy_signals,
            risk=legacy_risk,
            summary=legacy_summary,
            legacy_metrics=legacy_metrics_extra,
            strategy_version=strategy_version,
            quality_filter=quality_filter,
            scoring_mode=mode,
            timings_ms=timings_ms,
        )

    assert run_engine
    engine_started = time.monotonic()
    scoring = ScoringEngine.score(
        ctx,
        sleeve,
        quality_score=quality_score,
        apply_openbb=True,
        metrics=dict(features.enriched_metrics),
    )
    timings_ms["engine_ms"] = round((time.monotonic() - engine_started) * 1000.0, 2)
    _persist_engine_attribution(scoring, symbol=symbol, sleeve=sleeve)

    parity_record: StageBParityRecord | None = None
    if run_legacy and legacy_final is not None and legacy_signals is not None:
        parity_started = time.monotonic()
        parity_record = log_score_parity(
            symbol=symbol,
            sleeve=sleeve,
            legacy_score=legacy_final,
            engine_score=scoring.final_score,
            factors=scoring.factors,
            legacy_signals=legacy_signals,
            scan_id=scan_id,
        )
        timings_ms["parity_ms"] = round((time.monotonic() - parity_started) * 1000.0, 2)

    extra = legacy_metrics_extra if mode == "parity_sample" and run_legacy else {}
    return _build_engine_outcome(
        features=features,
        scoring=scoring,
        strategy_version=strategy_version,
        quality_filter=quality_filter,
        scoring_mode=mode,
        legacy_score=legacy_final,
        parity_record=parity_record,
        extra_metrics=extra,
        timings_ms=timings_ms,
    )
