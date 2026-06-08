"""Scan job orchestration with two-stage bulk screening."""
from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime

from config import MAX_CANDIDATES_PER_BUCKET, SCAN_RESULT_TTL, UNIVERSE_SCAN_BATCH_SIZE
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
from services.scan_display import enrich_scan_display, refresh_results_return_metrics

logger = logging.getLogger(__name__)

STAGE_B_TOP_N = 50


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
        candidates: list[StockResult] = []
        fallback_candidates: list[StockResult] = []

        try:
            # Stage A — bulk OHLC filter
            job.progress = 5.0
            period = "6mo" if job.bucket == Bucket.penny else "1y"
            bulk_hist = ps.download_batch(
                universe,
                period=period,
                max_runtime_seconds=45,
            )
            job.message = f"Stage A: filtered {len(bulk_hist)} symbols with price data"
            job.progress = 25.0

            stage_a = filter_universe_by_price(job.bucket, bulk_hist)
            if not stage_a:
                stage_a = [s for s in universe if s.upper() in bulk_hist][:STAGE_B_TOP_N]

            # Limit deep analysis count
            stage_b_symbols = stage_a[:STAGE_B_TOP_N]
            total = len(stage_b_symbols)
            job.message = f"Stage B: deep scoring top {total} candidates"

            for idx, symbol in enumerate(stage_b_symbols):
                job.progress = 25.0 + round((idx / max(total, 1)) * 70, 1)
                job.message = f"Scoring {symbol} ({idx + 1}/{total})"

                try:
                    ctx = screener.enrich(symbol)
                    if ctx is None:
                        hist = bulk_hist.get(symbol.upper())
                        if hist is None or hist.empty:
                            continue
                        from screeners.base import CandidateContext

                        ctx = build_candidate(
                            symbol,
                            history_period=period,
                            include_spy=job.bucket == Bucket.medium,
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
                        except Exception:
                            pass

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
                except Exception as exc:
                    logger.warning("Failed %s in %s scan: %s", symbol, job.bucket, exc)

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
            else:
                job.message = f"Found {len(job.results)} candidates"
            job.completed_at = datetime.utcnow()

            cache_module.save_scan_results(
                job.bucket.value,
                [r.model_dump(mode="json") for r in job.results],
                job.completed_at.isoformat(),
                SCAN_RESULT_TTL,
                strategy_version=strategy.version_id,
            )
            cache_module.save_scan_snapshot(
                bucket=job.bucket.value,
                results=[r.model_dump(mode="json") for r in job.results],
                options=options.model_dump(mode="json"),
                name=f"{job.bucket.value.title()} auto scan",
                strategy_version=strategy.version_id,
                completed_at=job.completed_at,
            )
        except Exception as exc:
            logger.exception("Scan failed: %s", exc)
            job.status = ScanStatus.failed
            job.error = str(exc)
            job.message = f"Scan failed: {exc}"

    def start_scan_async(self, bucket: Bucket, options: ScanOptions | None = None) -> ScanJob:
        job = self.create_job(bucket)
        thread = threading.Thread(target=self.run_scan, args=(job.job_id, options), daemon=True)
        thread.start()
        return job


scan_manager = ScanManager()
