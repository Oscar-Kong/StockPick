"""Scan job orchestration with two-stage bulk screening."""
from __future__ import annotations

import logging
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
from data.candidate_builder import build_candidate
from data.historical_store import HistoricalStore
from data.price_service import PriceService
from data.quality_filters import apply_quality_filters
from data.strategy_registry import StrategyRegistry
from data.universe import get_universe
from data.universe_builder import filter_universe_by_price
from models.schemas import Bucket, RiskLevel, ScanOptions, ScanStatus, StockResult
from scoring.data_quality import should_exclude_low_quality
from screeners.base import BaseScreener
from screeners.compounder import CompounderScreener
from screeners.medium import MediumScreener
from screeners.penny import PennyScreener
from services.scan_context import set_bulk_scan
from services.scan_display import enrich_scan_display, refresh_results_return_metrics

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
        if bucket == Bucket.penny:
            return PennyScreener()
        if bucket == Bucket.medium:
            return MediumScreener()
        return CompounderScreener()

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

        set_bulk_scan(True)
        try:
            # Stage A — bulk OHLC filter
            job.progress = 5.0
            period = "6mo" if job.bucket == Bucket.penny else "1y"
            bulk_hist = ps.download_batch(
                universe,
                period=period,
                max_runtime_seconds=SCAN_PRICE_DOWNLOAD_MAX_SECONDS,
            )
            job.timings["stage_a_ms"] = round((time.monotonic() - stage_a_started) * 1000.0, 1)
            job.message = f"Stage A: filtered {len(bulk_hist)} symbols with price data"
            job.progress = 25.0

            stage_a = filter_universe_by_price(job.bucket, bulk_hist)
            if not stage_a:
                stage_a = [s for s in universe if s.upper() in bulk_hist][:stage_b_cap]

            # Limit deep analysis count (mode-aware)
            stage_b_symbols = stage_a[:stage_b_cap]
            total = len(stage_b_symbols)
            job.message = f"Stage B: deep scoring top {total} candidates"
            parity_records: list = []
            stage_b_started = time.monotonic()

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
                    ctx = build_candidate(
                        symbol,
                        history_period=period,
                        include_spy=job.bucket == Bucket.medium,
                        reconcile=False,
                        price_service=ps,
                    )
                    if ctx is None:
                        hist = bulk_hist.get(symbol.upper())
                        if hist is None or hist.empty:
                            continue
                        ctx = build_candidate(
                            symbol,
                            history_period=period,
                            include_spy=job.bucket == Bucket.medium,
                            reconcile=False,
                            price_service=ps,
                        )
                        if ctx is None:
                            continue

                    # Keep a lightweight backup candidate so scans still return useful output
                    # when strict filters reject everything under provider-constrained data.
                    hist = ctx.history
                    if hist is not None and not hist.empty and len(hist) >= 21:
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
                            # Fallback candidate is a UX nicety — failure here must not
                            # kill the symbol's main scoring path. Log so we can spot
                            # regressions instead of swallowing silently.
                            logger.warning(
                                "Fallback candidate skipped for %s: %s", symbol, fb_exc
                            )

                    quality_score = ctx.info.get("_reconcile_quality")
                    hist_len = len(ctx.history) if ctx.history is not None else 0
                    exclude, exclude_reason = should_exclude_low_quality(quality_score, hist_len)
                    if exclude:
                        logger.debug("Excluded %s: %s", symbol, exclude_reason)
                        continue

                    if not screener.hard_filter(ctx, options):
                        continue

                    qf = apply_quality_filters(
                        symbol,
                        job.bucket,
                        ctx.price,
                        ctx.history,
                        ctx.info,
                    )
                    if not qf.passed:
                        logger.debug("Quality filter rejected %s: %s", symbol, qf.reasons)
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

                    result = screener.to_result(ctx, round(score, 1), signals, risk, summary, metrics)
                    candidates.append(result)
                    if outcome.parity_record is not None:
                        parity_records.append(outcome.parity_record)
                except Exception as exc:
                    logger.warning("Failed %s in %s scan: %s", symbol, job.bucket, exc)

            from config import USE_SCORING_ENGINE_IN_SCAN
            from services.scan_parity import aggregate_scan_parity_summary, log_scan_parity_summary

            job.timings["stage_b_ms"] = round((time.monotonic() - stage_b_started) * 1000.0, 1)
            parity_summary_obj = aggregate_scan_parity_summary(parity_records)
            if parity_summary_obj is not None:
                job.parity_summary = parity_summary_obj.to_dict()
                log_scan_parity_summary(parity_summary_obj, bucket=job.bucket.value)

            candidates.sort(key=lambda r: r.score, reverse=True)
            if not candidates and fallback_candidates:
                fallback_candidates.sort(key=lambda r: r.score, reverse=True)
                candidates = fallback_candidates
            job.results = candidates[:max_results]
            job.status = ScanStatus.completed
            job.progress = 100.0
            if job.results and not any(not r.metrics.get("provider_limited_partial_data") for r in job.results):
                job.message = (
                    f"Found {len(job.results)} candidates (partial-data fallback; provider-limited)"
                )
            elif parity_summary_obj is not None:
                job.message = (
                    f"Found {len(job.results)} candidates "
                    f"(ScoringEngine; avg parity delta {parity_summary_obj.average_delta:.1f})"
                )
            else:
                job.message = f"Found {len(job.results)} candidates"
            job.completed_at = datetime.utcnow()
            job.timings["total_ms"] = round((time.monotonic() - scan_started) * 1000.0, 1)
            job.timings["stage_b_candidates"] = float(total)
            job.timings["stage_b_mode"] = 1.0 if getattr(options, "mode", "deep") == "fast" else 0.0

            scan_metadata: dict = {"timings": dict(job.timings)}
            if job.parity_summary is not None:
                scan_metadata["scoring_engine_used"] = USE_SCORING_ENGINE_IN_SCAN
                scan_metadata["parity_summary"] = job.parity_summary

            cache_module.save_scan_results(
                job.bucket.value,
                [r.model_dump(mode="json") for r in job.results],
                job.completed_at.isoformat(),
                _ttl_for_bucket(job.bucket),
                strategy_version=strategy.version_id,
                metadata=scan_metadata,
            )
            cache_module.save_scan_snapshot(
                bucket=job.bucket.value,
                results=[r.model_dump(mode="json") for r in job.results],
                options=options.model_dump(mode="json"),
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
