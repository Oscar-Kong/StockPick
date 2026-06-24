#!/usr/bin/env python3
"""Run penny / medium / compounder scans with USE_SCORING_ENGINE_IN_SCAN=true and emit parity JSON.

Modes:
  full (default) — ScanManager.run_scan (live providers; may fall back on API errors)
  cached         — Stage B parity from historical_store only (no provider calls)

Set env before backend imports (see run-staging-scan-parity.sh). Does not change .env on disk.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd

# Must precede config import so dotenv does not override when already exported.
os.environ["SCAN_SCORING_MODE"] = "parity_sample"
os.environ["SCAN_PARITY_SAMPLE_RATE"] = "1.0"
os.environ.setdefault("USE_SCORING_ENGINE_IN_SCAN", "true")
os.environ.setdefault("APP_ENV", "staging")
os.environ.setdefault("SCORE_ENGINE_V2_ENABLED", "true")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import SCAN_PARITY_SAMPLE_RATE, SCAN_SCORING_MODE  # noqa: E402
from services.scan_scoring_config import resolve_scan_scoring_mode  # noqa: E402
from models.schemas import Bucket, ScanOptions  # noqa: E402
from screeners.base import CandidateContext  # noqa: E402
from services.scan_manager import ScanManager  # noqa: E402


def _top_deltas(records: list[dict], limit: int = 5) -> list[dict]:
    ranked = sorted(records, key=lambda r: r.get("parity_delta", 0), reverse=True)
    out = []
    for rec in ranked[:limit]:
        out.append(
            {
                "symbol": rec.get("symbol"),
                "legacy_score": rec.get("legacy_score"),
                "engine_score": rec.get("engine_score"),
                "parity_delta": rec.get("parity_delta"),
                "legacy_bucket": rec.get("legacy_recommendation_bucket"),
                "engine_bucket": rec.get("engine_recommendation_bucket"),
                "bucket_differs": rec.get("recommendation_bucket_differs"),
                "top_factors": rec.get("top_factor_contributions", [])[:3],
            }
        )
    return out


def _factor_drivers(records: list[dict], *, delta_threshold: float = 10.0) -> list[dict]:
    """Aggregate factor mentions among high-delta symbols."""
    from collections import Counter

    counter: Counter[str] = Counter()
    for rec in records:
        if rec.get("parity_delta", 0) < delta_threshold:
            continue
        for f in rec.get("top_factor_contributions") or []:
            fid = f.get("factor_id") or f.get("display_name") or "unknown"
            counter[fid] += 1
    return [{"factor_id": k, "high_delta_symbol_count": v} for k, v in counter.most_common(8)]


def _bucket_report_from_parity(
    bucket: Bucket,
    *,
    parity: dict,
    status: str,
    message: str,
    result_count: int,
    mode: str,
    fallback_only: bool = False,
    job_id: str | None = None,
) -> dict:
    records = parity.get("records") or []
    return {
        "bucket": bucket.value,
        "mode": mode,
        "job_id": job_id,
        "status": status,
        "completed": status == "completed",
        "message": message,
        "result_count": result_count,
        "fallback_only_results": fallback_only,
        "stage_b_candidates": parity.get("symbol_count", len(records)),
        "scoring_engine_used": bool(parity.get("scoring_engine_used", True)),
        "average_parity_delta": parity.get("average_delta"),
        "max_parity_delta": parity.get("max_delta"),
        "symbols_delta_gt_10": parity.get("symbols_delta_gt_10"),
        "recommendation_bucket_diffs": parity.get("recommendation_bucket_diffs"),
        "top_5_deltas": _top_deltas(records),
        "factor_drivers_high_delta": _factor_drivers(records),
        "ui_expectations": {
            "scoring_engine_v2_badge": bool(parity.get("scoring_engine_used")),
            "parity_summary_chip": parity.get("average_delta") is not None,
        },
    }


def _ctx_from_store(symbol: str, bucket: Bucket, *, min_bars: int = 90) -> CandidateContext | None:
    from data.historical_store import HistoricalStore
    from data.price_service import avg_volume_from_history

    rows = HistoricalStore().get_quotes(symbol.upper(), limit=max(min_bars + 30, 120))
    if len(rows) < min_bars:
        return None
    df = pd.DataFrame(rows)
    if "close" not in df.columns or "volume" not in df.columns:
        return None
    closes = df["close"].astype(float)
    avg_vol = avg_volume_from_history(df)
    mcap_by_bucket = {
        Bucket.penny: 200_000_000,
        Bucket.medium: 15_000_000_000,
        Bucket.compounder: 200_000_000_000,
    }
    return CandidateContext(
        symbol=symbol.upper(),
        price=float(closes.iloc[-1]),
        info={
            "sector": "Technology",
            "marketCap": mcap_by_bucket.get(bucket, 10_000_000_000),
            "averageVolume": avg_vol,
            "_reconcile_quality": 82.0,
        },
        fundamentals={},
        history=df,
    )


def run_bucket_cached_parity(bucket: Bucket, max_symbols: int) -> dict:
    """Stage B engine parity using local historical_store only (staging without live APIs)."""
    from data.quality_filters import apply_quality_filters
    from data.strategy_registry import StrategyRegistry
    from data.universe import get_universe
    from services.scan_parity import aggregate_scan_parity_summary
    from services.scan_scoring import score_stage_b_candidate

    manager = ScanManager()
    screener = manager._get_screener(bucket)
    strategy = StrategyRegistry().get_active(bucket.value)
    options = ScanOptions()
    records = []
    scored: list[tuple[str, float]] = []

    min_bars = {Bucket.penny: 90, Bucket.medium: 90, Bucket.compounder: 252}.get(bucket, 90)

    for sym in get_universe(bucket.value):
        if len(records) >= max_symbols:
            break
        ctx = _ctx_from_store(sym, bucket, min_bars=min_bars)
        if ctx is None:
            continue
        if not screener.hard_filter(ctx, options):
            continue
        qf = apply_quality_filters(sym, bucket, ctx.price, ctx.history, ctx.info)
        if not qf.passed:
            continue
        outcome = score_stage_b_candidate(
            ctx=ctx,
            screener=screener,
            bucket=bucket,
            symbol=sym,
            quality_score=ctx.info.get("_reconcile_quality"),
            strategy_version=strategy.version_id,
            quality_filter=qf.to_dict(),
        )
        if outcome.parity_record is not None:
            records.append(outcome.parity_record)
        scored.append((sym.upper(), outcome.score))

    summary = aggregate_scan_parity_summary(records)
    parity = summary.to_dict() if summary else {}
    scored.sort(key=lambda x: x[1], reverse=True)
    msg = (
        f"Cached Stage B parity: {len(records)} symbols scored (historical_store, engine path)"
        if records
        else "No symbols passed filters with cached history"
    )
    return _bucket_report_from_parity(
        bucket,
        parity=parity,
        status="completed" if records else "no_parity_data",
        message=msg,
        result_count=len(scored),
        mode="cached",
        fallback_only=False,
    )


def run_bucket(manager: ScanManager, bucket: Bucket, max_results: int) -> dict:
    job = manager.create_job(bucket)
    options = MagicMock()
    options.max_results = max_results
    options.model_dump.return_value = {"max_results": max_results}
    manager.run_scan(job.job_id, options)
    finished = manager.get_job(job.job_id)
    if finished is None:
        return {"bucket": bucket.value, "status": "unknown", "error": "job missing"}

    parity = finished.parity_summary or {}
    records = parity.get("records") or []
    fallback_only = bool(
        finished.results
        and all(r.metrics.get("provider_limited_partial_data") for r in finished.results)
    )

    return _bucket_report_from_parity(
        bucket,
        parity=parity,
        status=finished.status.value if hasattr(finished.status, "value") else str(finished.status),
        message=finished.message,
        result_count=len(finished.results or []),
        mode="full",
        fallback_only=fallback_only,
        job_id=finished.job_id,
    )


def _json_safe(obj):
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_json_safe(v) for v in obj]
    if hasattr(obj, "value") and not isinstance(obj, (str, int, float, bool)):
        return obj.value
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    return str(obj)


def main() -> int:
    parser = argparse.ArgumentParser(description="Staging scan parity report")
    parser.add_argument(
        "--mode",
        choices=("full", "cached"),
        default=os.getenv("STAGING_SCAN_MODE", "cached"),
        help="full=ScanManager (live APIs); cached=historical_store Stage B parity",
    )
    parser.add_argument(
        "--max-symbols",
        type=int,
        default=int(os.getenv("STAGING_CACHED_MAX_SYMBOLS", "12")),
        help="Max Stage B symbols per bucket in cached mode",
    )
    args = parser.parse_args()

    mode = resolve_scan_scoring_mode()
    if mode not in ("engine", "parity_sample"):
        print(
            json.dumps(
                {
                    "error": f"SCAN_SCORING_MODE={mode!r} — set parity_sample or engine for staging",
                    "hint": "source scripts/staging-scan-engine.env",
                },
                indent=2,
            )
        )
        return 1

    max_results = int(os.getenv("STAGING_SCAN_MAX_RESULTS", "25"))
    manager = ScanManager()
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "app_env": os.getenv("APP_ENV", "staging"),
        "scan_scoring_mode": mode,
        "scan_parity_sample_rate": SCAN_PARITY_SAMPLE_RATE if mode == "parity_sample" else None,
        "mode": args.mode,
        "max_results": max_results,
        "buckets": [],
    }

    for bucket in (Bucket.penny, Bucket.medium, Bucket.compounder):
        print(f"Running staging scan ({args.mode}): {bucket.value}...", file=sys.stderr)
        if args.mode == "cached":
            report["buckets"].append(run_bucket_cached_parity(bucket, args.max_symbols))
        else:
            report["buckets"].append(run_bucket(manager, bucket, max_results))

    out_path = Path(__file__).resolve().parents[2] / "storage" / "staging" / "scan_engine_parity_report.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(_json_safe(report), indent=2), encoding="utf-8")
    print(json.dumps(_json_safe(report), indent=2))
    print(f"\nWrote {out_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
