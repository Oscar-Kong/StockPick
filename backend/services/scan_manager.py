"""Scan job orchestration with two-stage bulk screening."""
from __future__ import annotations

import logging
import math
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime

from config import (
    MAX_CANDIDATES_PER_BUCKET,
    SCAN_PRICE_DOWNLOAD_MAX_SECONDS,
    SCAN_RESULT_TTL,
    SCAN_RESULT_TTL_COMPOUNDER,
    SCAN_RESULT_TTL_PENNY,
    SCAN_STAGE_B_TIME_BUDGET_SECONDS,
    SCAN_STAGE_B_TOP_N,
    SCAN_STAGE_B_TOP_N_FAST,
    UNIVERSE_SCAN_BATCH_SIZE,
)
from data import cache as cache_module
from data.candidate_builder import (
    HISTORY_SOURCE_BULK,
    HISTORY_SOURCE_PROVIDER,
    build_candidate,
)
from data.history_normalize import validate_preloaded_history
from data.historical_store import HistoricalStore
from data.price_service import PriceService
from data.quality_filters import apply_quality_filters
from data.strategy_registry import StrategyRegistry
from data.universe import get_universe
from models.schemas import Bucket, RiskLevel, ScanOptions, ScanStatus, StockResult
from scoring.data_quality import should_exclude_low_quality
from screeners.base import BaseScreener, CandidateContext
from core.sleeve import normalize_sleeve
from screeners.compounder import CompounderScreener
from screeners.penny import PennyScreener
from services.scan_context import set_bulk_scan
from services.scan_display import enrich_scan_display, refresh_results_return_metrics
from services.scan_data_flow import ScanDataFlowMetrics
from services.scan_skip_reasons import (
    CANDIDATE_BUILD_EXCEPTION,
    INVALID_PRICE,
    MISSING_HISTORY,
    PROVIDER_FAILURE,
    STRICT_FILTER_REJECTION,
    map_quality_exclusion_reason,
    record_scan_skip,
)
from services.scan_history_config import (
    bulk_history_reusable,
    compounder_stage_b_needs_fundamentals,
    stage_a_period,
    stage_b_min_history_bars,
    stage_b_period,
)
from services.stage_a_ranking import (
    rank_stage_a_candidates,
    select_stage_b_symbols,
)
from services.scan_trade_hint import attach_trade_hint_to_metrics
from services.scan_scoring_config import primary_scorer_is_engine, resolve_scan_scoring_mode
from services.scan_decomposition import build_decomposed_scores
from services.scan_final_ranking import apply_final_scan_ranking
from services.scan_issuer import issuer_key
from utils.pydantic_util import model_to_dict, models_to_dicts

logger = logging.getLogger(__name__)

# Backwards-compatible alias; tests patch this symbol directly. New code should
# read SCAN_STAGE_B_TOP_N from config.
STAGE_B_TOP_N = SCAN_STAGE_B_TOP_N


def _ttl_for_bucket(bucket: Bucket) -> int:
    if bucket == Bucket.penny:
        return SCAN_RESULT_TTL_PENNY
    if bucket == Bucket.compounder:
        return SCAN_RESULT_TTL_COMPOUNDER
    return SCAN_RESULT_TTL


def _stage_b_cap(mode: str) -> int:
    if (mode or "deep").lower() == "fast":
        return SCAN_STAGE_B_TOP_N_FAST
    return SCAN_STAGE_B_TOP_N


def _resolve_stage_b_context(
    symbol: str,
    *,
    stage_b_period: str,
    stage_a_period: str,
    include_spy: bool,
    price_service: PriceService,
    bulk_hist: dict,
    skipped: list[dict],
    flow: ScanDataFlowMetrics,
    bucket: Bucket,
) -> CandidateContext | None:
    """Build candidate context; compounder Stage B loads 5y history + cached fundamentals."""
    sym = symbol.upper()
    build_started = time.monotonic()
    bulk_frame = bulk_hist.get(sym)
    use_bulk = False
    normalized_bulk = None
    min_bars = stage_b_min_history_bars(bucket, stage_b_period)
    reconcile = compounder_stage_b_needs_fundamentals(bucket)
    fundamentals_policy = "cache_first" if reconcile else "live"

    if bulk_frame is not None and not bulk_frame.empty:
        bulk_bars = len(bulk_frame)
        if bulk_history_reusable(
            bucket,
            bulk_bars=bulk_bars,
            stage_a_period=stage_a_period,
            stage_b_period=stage_b_period,
        ):
            ok, reject_reason, normalized_bulk = validate_preloaded_history(
                bulk_frame,
                stage_b_period,
                require_fresh=False,
                min_bars=min_bars,
            )
            if ok and normalized_bulk is not None:
                use_bulk = True
            else:
                logger.info(
                    "Bulk history unusable for %s (%s); reloading %s OHLC",
                    sym,
                    reject_reason,
                    stage_b_period,
                )
        else:
            logger.debug(
                "Bulk history for %s has %s bars — insufficient for Stage B %s",
                sym,
                bulk_bars,
                stage_b_period,
            )

    ctx: CandidateContext | None = None
    try:
        flow.candidate_build_calls += 1
        if use_bulk:
            flow.bulk_cache_hits += 1
            ctx = build_candidate(
                sym,
                history_period=stage_b_period,
                include_spy=include_spy,
                reconcile=reconcile,
                fundamentals_policy=fundamentals_policy,
                price_service=price_service,
                history=normalized_bulk,
                history_source=HISTORY_SOURCE_BULK,
            )
        else:
            flow.provider_fallbacks += 1
            flow.history_reload_count += 1
            ctx = build_candidate(
                sym,
                history_period=stage_b_period,
                include_spy=include_spy,
                reconcile=reconcile,
                fundamentals_policy=fundamentals_policy,
                price_service=price_service,
                history_source=HISTORY_SOURCE_PROVIDER,
            )

        if ctx is None and use_bulk:
            flow.provider_fallbacks += 1
            flow.history_reload_count += 1
            flow.candidate_build_calls += 1
            ctx = build_candidate(
                sym,
                history_period=stage_b_period,
                include_spy=include_spy,
                reconcile=reconcile,
                fundamentals_policy=fundamentals_policy,
                price_service=price_service,
                history_source=HISTORY_SOURCE_PROVIDER,
            )
    except Exception as exc:
        record_scan_skip(
            skipped,
            symbol=sym,
            reason=CANDIDATE_BUILD_EXCEPTION,
            detail=str(exc),
        )
        logger.warning("Candidate build failed for %s: %s", sym, exc)
        flow.stage_b_build_ms += round((time.monotonic() - build_started) * 1000.0, 1)
        return None

    flow.stage_b_build_ms += round((time.monotonic() - build_started) * 1000.0, 1)

    if ctx is None:
        if bulk_frame is None or bulk_frame.empty:
            record_scan_skip(skipped, symbol=sym, reason=MISSING_HISTORY)
        else:
            record_scan_skip(skipped, symbol=sym, reason=PROVIDER_FAILURE)
        return None

    if reconcile:
        if ctx.info.get("_fundamental_from_cache"):
            flow.fundamental_cache_hits += 1
        elif ctx.info.get("_fundamental_refreshed"):
            flow.fundamental_refreshes += 1

    flow.record_candidate_source(sym, str(ctx.info.get("_history_source", "unknown")))
    diag = dict(ctx.info.get("_scan_diagnostics") or {})
    diag["stage_a_period"] = stage_a_period
    diag["stage_b_period"] = stage_b_period
    flow.record_candidate_diagnostics(sym, diag)
    return ctx


def _append_partial_data_fallback(
    *,
    ctx: CandidateContext,
    symbol: str,
    job: ScanJob,
    screener: BaseScreener,
    strategy,
    quality_score: float | None,
    fallback_candidates: list[StockResult],
) -> None:
    """Keep a lightweight backup candidate when strict filters reject everything."""
    hist = ctx.history
    if hist is None or hist.empty or len(hist) < 21:
        return
    try:
        close = hist["close"]
        vol = hist["volume"]
        ret_20 = float(close.iloc[-1] / close.iloc[-20] - 1.0) * 100.0
        vol_ratio = float(vol.tail(5).mean() / max(vol.tail(20).mean(), 1.0))
        fallback_score = max(
            0.0,
            min(100.0, 50.0 + (ret_20 * 1.8) + ((vol_ratio - 1.0) * 12.0)),
        )
        fallback_metrics = {
            "strategy_version": strategy.version_id,
            "provider_limited_partial_data": True,
            "fallback_ret_20d_pct": round(ret_20, 2),
            "fallback_volume_ratio_5d_20d": round(vol_ratio, 2),
            "fallback_reason": "strict filters rejected all candidates with current provider data",
        }
        fallback_risk = RiskLevel.high if job.bucket == Bucket.penny else RiskLevel.medium
        fallback_summary, fallback_metrics = enrich_scan_display(
            ctx.info,
            ctx.fundamentals,
            ctx.history,
            fallback_metrics,
            legacy_summary="Partial-data candidate — verify before trading.",
        )
        fallback_metrics = attach_trade_hint_to_metrics(
            fallback_metrics,
            score=round(fallback_score, 1),
            sleeve=job.bucket.value,
            risk_level=fallback_risk,
            data_quality_score=quality_score,
            provider_limited=True,
        )
        fallback_candidates.append(
            screener.to_result(
                ctx=ctx,
                score=round(fallback_score, 1),
                signals=[],
                risk=fallback_risk,
                summary=fallback_summary,
                metrics=fallback_metrics,
            )
        )
    except Exception as fb_exc:
        logger.warning("Fallback candidate skipped for %s: %s", symbol, fb_exc)


@dataclass
class ScanJob:
    job_id: str
    bucket: Bucket
    status: ScanStatus = ScanStatus.pending
    progress: float = 0.0
    message: str = ""
    results: list[StockResult] = field(default_factory=list)
    completed_at: datetime | None = None
    error: str | None = None
    parity_summary: dict | None = None
    timings: dict[str, float] = field(default_factory=dict)
    scoring_engine_used: bool | None = None
    scoring_mode: str | None = None


class ScanManager:
    def __init__(self):
        self._jobs: dict[str, ScanJob] = {}
        self._lock = threading.Lock()

    def create_job(self, bucket: Bucket) -> ScanJob:
        job = ScanJob(job_id=str(uuid.uuid4()), bucket=bucket)
        with self._lock:
            self._jobs[job.job_id] = job
        return job

    def get_job(self, job_id: str) -> ScanJob | None:
        with self._lock:
            return self._jobs.get(job_id)

    def get_latest_scan(self, bucket: Bucket) -> dict | None:
        latest = cache_module.get_latest_scan(bucket.value)
        if latest:
            results = latest.get("results", [])
            if results and isinstance(results[0], dict):
                latest = {**latest, "results": refresh_results_return_metrics(results)}
            return latest
        saved = cache_module.list_saved_scans(bucket=bucket.value, limit=1)
        if saved:
            row = saved[0]
            results = row.get("results", [])
            if results and isinstance(results[0], dict):
                results = refresh_results_return_metrics(results)
            return {
                "results": results,
                "completed_at": row.get("completed_at") or row.get("created_at"),
                "strategy_version": row.get("strategy_version"),
            }
        return None

    def _get_screener(self, bucket: Bucket) -> BaseScreener:
        sleeve = normalize_sleeve(bucket.value)
        if sleeve == "compounder":
            return CompounderScreener()
        return PennyScreener()

    def run_scan(self, job_id: str, options: ScanOptions | None = None) -> None:
        options = options or ScanOptions()
        job = self.get_job(job_id)
        if not job:
            return

        job.status = ScanStatus.running
        job.message = "Stage A: bulk price download..."
        screener = self._get_screener(job.bucket)
        strategy = StrategyRegistry().get_active(job.bucket.value)
        ps = PriceService()
        # Share price service with screener when supported
        if hasattr(screener, "ps"):
            screener.ps = ps
        universe = get_universe(job.bucket.value)
        if UNIVERSE_SCAN_BATCH_SIZE > 0:
            universe = universe[:UNIVERSE_SCAN_BATCH_SIZE]
        max_results = min(options.max_results, MAX_CANDIDATES_PER_BUCKET)
        stage_b_cap = _stage_b_cap(getattr(options, "mode", "deep"))
        candidates: list[StockResult] = []
        fallback_candidates: list[StockResult] = []
        scan_started = time.monotonic()
        stage_a_started = scan_started
        flow_metrics = ScanDataFlowMetrics()

        set_bulk_scan(True)
        try:
            # Stage A — bulk OHLC download
            job.progress = 5.0
            period_a = stage_a_period(job.bucket)
            period_b = stage_b_period(job.bucket)
            bulk_download_started = time.monotonic()
            bulk_hist = ps.download_batch(
                universe,
                period=period_a,
                max_runtime_seconds=SCAN_PRICE_DOWNLOAD_MAX_SECONDS,
            )
            flow_metrics.bulk_download_ms = round((time.monotonic() - bulk_download_started) * 1000.0, 1)
            flow_metrics.bulk_symbols_returned = len(bulk_hist)
            job.timings["stage_a_bulk_download_ms"] = flow_metrics.bulk_download_ms
            job.timings["stage_a_bulk_symbols"] = float(flow_metrics.bulk_symbols_returned)

            rank_started = time.monotonic()
            stage_a_result = rank_stage_a_candidates(job.bucket, bulk_hist, universe=universe)
            if not stage_a_result.ranked:
                fallback_universe = [s.upper() for s in universe if s.upper() in bulk_hist]
                logger.warning(
                    "Stage A ranked zero with eligibility — retrying %s symbols with history only",
                    len(fallback_universe),
                )
                stage_a_result = rank_stage_a_candidates(
                    job.bucket,
                    bulk_hist,
                    universe=fallback_universe,
                    apply_eligibility=True,
                )
            flow_metrics.stage_a_rank_ms = round((time.monotonic() - rank_started) * 1000.0, 1)
            job.timings["stage_a_rank_ms"] = flow_metrics.stage_a_rank_ms
            job.timings["stage_a_ms"] = round((time.monotonic() - stage_a_started) * 1000.0, 1)
            job.progress = 25.0

            stage_b_symbols = select_stage_b_symbols(stage_a_result.ranked, stage_b_cap)
            total = len(stage_b_symbols)
            job.timings["stage_a_eligible"] = float(len(stage_a_result.ranked))
            job.timings["stage_a_excluded"] = float(len(stage_a_result.excluded))
            job.message = (
                f"Stage A: ranked {len(stage_a_result.ranked)} eligible; "
                f"Stage B scoring top {total}"
            )
            parity_records: list = []
            stage_b_started = time.monotonic()
            skipped_candidates: list[dict] = []
            scoring_timing_totals = {
                "enrich_ms": 0.0,
                "legacy_ms": 0.0,
                "engine_ms": 0.0,
                "parity_ms": 0.0,
            }
            legacy_invocations = 0
            engine_invocations = 0
            parity_sampled_count = 0

            scoring_mode = resolve_scan_scoring_mode()

            for idx, symbol in enumerate(stage_b_symbols):
                if (
                    SCAN_STAGE_B_TIME_BUDGET_SECONDS > 0
                    and (time.monotonic() - stage_b_started) >= SCAN_STAGE_B_TIME_BUDGET_SECONDS
                ):
                    job.message = (
                        f"Stage B time budget reached; scored {len(candidates)} of {total}"
                    )
                    break

                job.progress = 25.0 + round((idx / max(total, 1)) * 70, 1)
                job.message = f"Scoring {symbol} ({idx + 1}/{total})"

                try:
                    ctx = _resolve_stage_b_context(
                        symbol,
                        stage_b_period=period_b,
                        stage_a_period=period_a,
                        include_spy=job.bucket == Bucket.medium,
                        price_service=ps,
                        bulk_hist=bulk_hist,
                        skipped=skipped_candidates,
                        flow=flow_metrics,
                        bucket=job.bucket,
                    )
                    if ctx is None:
                        continue

                    quality_score = ctx.info.get("_reconcile_quality")
                    hist_len = len(ctx.history) if ctx.history is not None else 0

                    price = ctx.price
                    if price is None or not math.isfinite(float(price)) or float(price) <= 0:
                        record_scan_skip(
                            skipped_candidates,
                            symbol=symbol,
                            reason=INVALID_PRICE,
                            detail=str(price),
                        )
                        continue

                    _append_partial_data_fallback(
                        ctx=ctx,
                        symbol=symbol,
                        job=job,
                        screener=screener,
                        strategy=strategy,
                        quality_score=quality_score,
                        fallback_candidates=fallback_candidates,
                    )

                    exclude, exclude_reason = should_exclude_low_quality(quality_score, hist_len)
                    if exclude:
                        record_scan_skip(
                            skipped_candidates,
                            symbol=symbol,
                            reason=map_quality_exclusion_reason(exclude_reason, hist_len),
                            detail=exclude_reason,
                        )
                        logger.info("Excluded %s: %s", symbol, exclude_reason)
                        continue

                    if not screener.hard_filter(ctx, options):
                        record_scan_skip(
                            skipped_candidates,
                            symbol=symbol,
                            reason=STRICT_FILTER_REJECTION,
                            detail="hard_filter",
                        )
                        continue

                    qf = apply_quality_filters(
                        symbol,
                        job.bucket,
                        ctx.price,
                        ctx.history,
                        ctx.info,
                    )
                    if not qf.passed:
                        record_scan_skip(
                            skipped_candidates,
                            symbol=symbol,
                            reason=STRICT_FILTER_REJECTION,
                            detail="; ".join(qf.reasons) if qf.reasons else "quality_filter",
                        )
                        logger.info("Quality filter rejected %s: %s", symbol, qf.reasons)
                        continue

                    from services.scan_scoring import score_stage_b_candidate

                    outcome = score_stage_b_candidate(
                        ctx=ctx,
                        screener=screener,
                        bucket=job.bucket,
                        symbol=symbol,
                        quality_score=quality_score,
                        strategy_version=strategy.version_id,
                        quality_filter=qf.to_dict(),
                        scan_id=job.job_id,
                        scoring_mode=scoring_mode,
                    )
                    score = outcome.score
                    signals = outcome.signals
                    risk = outcome.risk
                    summary = outcome.summary
                    metrics = outcome.metrics
                    raw_score = outcome.raw_score

                    HistoricalStore().save_factor_snapshot(
                        symbol,
                        job.bucket.value,
                        strategy.version_id,
                        {s.name: s.value for s in signals},
                        score=score,
                    )
                    summary, metrics = enrich_scan_display(
                        ctx.info,
                        ctx.fundamentals,
                        ctx.history,
                        metrics,
                        legacy_summary=summary,
                    )

                    hist_len = len(ctx.history) if ctx.history is not None else 0
                    decomposed = build_decomposed_scores(
                        raw_score=raw_score,
                        signals=signals,
                        metrics=metrics,
                        bucket=job.bucket,
                        price=float(ctx.price),
                        history=ctx.history,
                        quality_score=quality_score,
                        hist_len=hist_len,
                    )
                    metrics.update(decomposed.to_metrics_dict())
                    metrics["_issuer_key"] = issuer_key(symbol, ctx.info)
                    metrics = attach_trade_hint_to_metrics(
                        metrics,
                        score=round(decomposed.ranking_score, 1),
                        sleeve=job.bucket.value,
                        risk_level=risk,
                        data_quality_score=quality_score,
                    )
                    ranking_score = decomposed.ranking_score

                    result = screener.to_result(
                        ctx,
                        round(ranking_score, 1),
                        signals,
                        risk,
                        summary,
                        metrics,
                    )
                    result.alpha_score = decomposed.alpha_score
                    result.confidence_score = decomposed.confidence_score
                    result.tradability_score = decomposed.tradability_score
                    result.ranking_score = decomposed.ranking_score
                    candidates.append(result)
                    if outcome.parity_record is not None:
                        parity_records.append(outcome.parity_record)
                    for timing_key in scoring_timing_totals:
                        scoring_timing_totals[timing_key] += float(
                            outcome.timings_ms.get(timing_key, 0.0)
                        )
                    if outcome.legacy_invoked:
                        legacy_invocations += 1
                    if outcome.engine_invoked:
                        engine_invocations += 1
                    if outcome.parity_sampled:
                        parity_sampled_count += 1
                except Exception as exc:
                    record_scan_skip(
                        skipped_candidates,
                        symbol=symbol,
                        reason=CANDIDATE_BUILD_EXCEPTION,
                        detail=str(exc),
                    )
                    logger.warning("Failed %s in %s scan: %s", symbol, job.bucket, exc)

            from config import SCAN_PARITY_SAMPLE_RATE
            from services.scan_parity import aggregate_scan_parity_summary, log_scan_parity_summary

            job.timings["stage_b_ms"] = round((time.monotonic() - stage_b_started) * 1000.0, 1)
            job.timings["stage_b_candidate_build_ms"] = flow_metrics.stage_b_build_ms
            job.timings["stage_b_bulk_cache_hits"] = float(flow_metrics.bulk_cache_hits)
            job.timings["stage_b_provider_fallbacks"] = float(flow_metrics.provider_fallbacks)
            job.timings["stage_b_history_reloads"] = float(flow_metrics.history_reload_count)
            job.timings["stage_b_candidate_build_calls"] = float(flow_metrics.candidate_build_calls)
            parity_summary_obj = aggregate_scan_parity_summary(
                parity_records,
                scoring_mode=scoring_mode,
                sample_rate=SCAN_PARITY_SAMPLE_RATE if scoring_mode == "parity_sample" else None,
            )
            if parity_summary_obj is not None:
                job.parity_summary = parity_summary_obj.to_dict()
                log_scan_parity_summary(parity_summary_obj, bucket=job.bucket.value)

            previous_scan = cache_module.get_latest_scan(job.bucket.value)
            previous_rows = (previous_scan or {}).get("results") or []

            ranking_out = apply_final_scan_ranking(
                candidates,
                bucket=job.bucket,
                max_results=max_results,
                bulk_hist=bulk_hist,
                previous_results=previous_rows,
            )
            if not ranking_out.results and fallback_candidates:
                fallback_ranked = apply_final_scan_ranking(
                    fallback_candidates,
                    bucket=job.bucket,
                    max_results=max_results,
                    bulk_hist=bulk_hist,
                    previous_results=previous_rows,
                )
                job.results = fallback_ranked.results
                ranking_meta = fallback_ranked.to_metadata()
            else:
                job.results = ranking_out.results
                ranking_meta = ranking_out.to_metadata()
            job.status = ScanStatus.completed
            job.progress = 100.0
            if job.results and not any(not r.metrics.get("provider_limited_partial_data") for r in job.results):
                job.message = (
                    f"Found {len(job.results)} candidates (partial-data fallback; provider-limited)"
                )
            elif parity_summary_obj is not None:
                job.message = (
                    f"Found {len(job.results)} candidates "
                    f"({scoring_mode}; parity n={parity_summary_obj.symbol_count}, "
                    f"avg delta {parity_summary_obj.average_delta:.1f})"
                )
            elif primary_scorer_is_engine(scoring_mode):
                job.message = f"Found {len(job.results)} candidates (ScoringEngine/{scoring_mode})"
            else:
                job.message = f"Found {len(job.results)} candidates"
            job.completed_at = datetime.utcnow()
            job.timings["total_ms"] = round((time.monotonic() - scan_started) * 1000.0, 1)
            job.timings["stage_b_candidates"] = float(total)
            job.timings["stage_b_mode"] = 1.0 if getattr(options, "mode", "deep") == "fast" else 0.0

            job.timings["stage_b_scoring_enrich_ms"] = round(scoring_timing_totals["enrich_ms"], 1)
            job.timings["stage_b_scoring_legacy_ms"] = round(scoring_timing_totals["legacy_ms"], 1)
            job.timings["stage_b_scoring_engine_ms"] = round(scoring_timing_totals["engine_ms"], 1)
            job.timings["stage_b_scoring_parity_ms"] = round(scoring_timing_totals["parity_ms"], 1)
            job.timings["stage_b_scoring_legacy_calls"] = float(legacy_invocations)
            job.timings["stage_b_scoring_engine_calls"] = float(engine_invocations)
            job.timings["stage_b_parity_sampled"] = float(parity_sampled_count)
            job.timings["stage_b_scoring_mode"] = {"legacy": 0.0, "engine": 1.0, "parity_sample": 2.0}.get(
                scoring_mode, 0.0
            )

            scan_metadata: dict = {"timings": dict(job.timings)}
            scan_metadata["stage_a_diagnostics"] = stage_a_result.to_diagnostics(advanced_count=total)
            scan_metadata["data_flow"] = flow_metrics.to_dict()
            scan_metadata["history_horizons"] = {
                "stage_a_period": period_a,
                "stage_b_period": period_b,
                "bucket": job.bucket.value,
            }
            if skipped_candidates:
                scan_metadata["skipped_candidates"] = skipped_candidates
                scan_metadata["skipped_count"] = float(len(skipped_candidates))
            scan_metadata["scoring_mode"] = scoring_mode
            job.scoring_mode = scoring_mode
            job.scoring_engine_used = primary_scorer_is_engine(scoring_mode)
            scan_metadata["scoring_engine_used"] = job.scoring_engine_used
            if scoring_mode == "parity_sample":
                scan_metadata["parity_sample_rate"] = SCAN_PARITY_SAMPLE_RATE
            if job.parity_summary is not None:
                scan_metadata["parity_summary"] = job.parity_summary
            scan_metadata["ranking_diagnostics"] = ranking_meta

            cache_module.save_scan_results(
                job.bucket.value,
                models_to_dicts(job.results),
                job.completed_at.isoformat(),
                _ttl_for_bucket(job.bucket),
                strategy_version=strategy.version_id,
                metadata=scan_metadata,
            )
            cache_module.save_scan_snapshot(
                bucket=job.bucket.value,
                results=models_to_dicts(job.results),
                options=model_to_dict(options),
                name=f"{job.bucket.value.title()} auto scan",
                strategy_version=strategy.version_id,
                completed_at=job.completed_at,
            )
            # A successful scan supersedes any prior failed-attempt marker.
            try:
                cache_module.clear_scan_attempt_failure(job.bucket.value)
            except Exception as clear_exc:
                logger.warning(
                    "Failed to clear scan_attempt_failure marker for %s: %s",
                    job.bucket.value,
                    clear_exc,
                )
        except Exception as exc:
            logger.exception("Scan failed: %s", exc)
            job.status = ScanStatus.failed
            job.error = str(exc)
            job.message = f"Scan failed: {exc}"
            job.timings["total_ms"] = round((time.monotonic() - scan_started) * 1000.0, 1)
            # Stamp a separate marker so /scan/latest/{bucket} can show
            # "last attempt failed" without overwriting the prior successful results.
            try:
                cache_module.record_scan_attempt_failure(job.bucket.value, str(exc))
            except Exception as marker_exc:
                logger.warning(
                    "Failed to record scan_attempt_failure marker for %s: %s",
                    job.bucket.value,
                    marker_exc,
                )
        finally:
            set_bulk_scan(False)

    def start_scan_async(self, bucket: Bucket, options: ScanOptions | None = None) -> ScanJob:
        job = self.create_job(bucket)
        thread = threading.Thread(target=self.run_scan, args=(job.job_id, options), daemon=True)
        thread.start()
        return job


scan_manager = ScanManager()
