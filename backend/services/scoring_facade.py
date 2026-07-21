"""Canonical scoring facade.

Single entry point used by every code path that needs a "final score" for a
symbol so Scan, Watchlist, and Analyze never disagree on the same input.

Why a facade (and not a refactor of `score_stage_b_candidate` directly)?
- `score_stage_b_candidate` already implements the legacy + ScoringEngine
  parity logic and is exercised by `tests/test_scan_manager_integration.py`
  and `tests/test_scan_scoring_engine_parity.py`. We do not want to change
  its signature or behavior in this slice.
- Watchlist's `analyze_symbol` historically duplicated the same DQ → enrich →
  OpenBB pipeline by hand, which caused subtle drift (e.g. metrics shape).

This module wraps `score_stage_b_candidate` and accepts the smaller argument
set that non-scan callers usually have. `quality_filter` defaults to `{}` and
`strategy_version` defaults to the active strategy for the bucket so callers
that do not care about scan-only bookkeeping fields can ignore them.

The numeric `score`, `risk`, and signal list produced here are guaranteed to
match what Scan Stage B produces for the same `CandidateContext`. If
`SCAN_SCORING_MODE=engine`, both Scan and Watchlist switch to the ScoringEngine in lockstep — no
more "same symbol, two scores" drift. Use `parity_sample` during migration to compare legacy vs engine on a sample without doubling work for every symbol.
"""
from __future__ import annotations

import logging
from typing import Any

from models.schemas import Bucket
from screeners.base import BaseScreener, CandidateContext
from services.scan_scoring import ScanScoreOutcome, score_stage_b_candidate

logger = logging.getLogger(__name__)


def _coerce_bucket(bucket: Bucket | str) -> Bucket:
    if isinstance(bucket, Bucket):
        return bucket
    return Bucket(str(bucket).strip().lower())


def _strategy_version_for(bucket: Bucket | str) -> str:
    """Best-effort lookup of the active strategy version for `bucket`."""
    try:
        from data.strategy_registry import StrategyRegistry

        sleeve = bucket.value if isinstance(bucket, Bucket) else str(bucket)
        return StrategyRegistry().get_active(sleeve).version_id
    except Exception as exc:  # pragma: no cover — defensive
        logger.warning("Falling back to default strategy version for %s: %s", bucket, exc)
        from config import STRATEGY_VERSION

        return STRATEGY_VERSION


def score_symbol_canonical(
    *,
    ctx: CandidateContext,
    screener: BaseScreener,
    bucket: Bucket | str,
    symbol: str | None = None,
    quality_score: float | None = None,
    strategy_version: str | None = None,
    quality_filter: dict[str, Any] | None = None,
) -> ScanScoreOutcome:
    """Compute the canonical score for one candidate.

    Same numeric output as Scan Stage B for the same input. Callers that lack
    a `quality_filter` (Watchlist, Analyze) can omit it; we record an empty
    dict so downstream `metrics["quality_filter"]` is always present.
    """
    bucket_enum = _coerce_bucket(bucket)
    sym = (symbol or ctx.symbol or "").upper()
    sv = strategy_version or _strategy_version_for(bucket_enum)
    qf = quality_filter if quality_filter is not None else {}
    return score_stage_b_candidate(
        ctx=ctx,
        screener=screener,
        bucket=bucket_enum,
        symbol=sym,
        quality_score=quality_score,
        strategy_version=sv,
        quality_filter=qf,
    )
