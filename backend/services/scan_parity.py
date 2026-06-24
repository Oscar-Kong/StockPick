"""Structured legacy vs ScoringEngine parity for Stage B scans."""
from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from config import FACTOR_MODEL_VERSION
from engines.recommendation.engine import recommendation_label_from_score
from screeners.base import WeightedSignal

logger = logging.getLogger(__name__)

PARITY_DELTA_ALERT_THRESHOLD = 10.0
TOP_FACTOR_CONTRIBUTION_COUNT = 5


@dataclass
class StageBParityRecord:
    symbol: str
    sleeve: str
    legacy_score: float
    engine_score: float
    parity_delta: float
    scoring_engine_used: bool
    top_factor_contributions: list[dict[str, Any]] = field(default_factory=list)
    legacy_recommendation_bucket: str = ""
    engine_recommendation_bucket: str = ""
    recommendation_bucket_differs: bool = False
    scan_id: str = ""
    timestamp: str = ""
    scoring_version: str = ""
    factor_differences: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ScanParitySummary:
    scoring_engine_used: bool
    symbol_count: int
    average_delta: float
    max_delta: float
    symbols_delta_gt_10: int
    recommendation_bucket_diffs: int
    records: list[StageBParityRecord] = field(default_factory=list)
    scoring_mode: str = "parity_sample"
    sample_rate: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "scoring_engine_used": self.scoring_engine_used,
            "symbol_count": self.symbol_count,
            "average_delta": self.average_delta,
            "max_delta": self.max_delta,
            "symbols_delta_gt_10": self.symbols_delta_gt_10,
            "recommendation_bucket_diffs": self.recommendation_bucket_diffs,
            "scoring_mode": self.scoring_mode,
            "sample_rate": self.sample_rate,
            "records": [r.to_dict() for r in self.records],
        }


def top_factor_contributions(factors: list[Any], *, limit: int = TOP_FACTOR_CONTRIBUTION_COUNT) -> list[dict[str, Any]]:
    """Return top factor rows sorted by absolute contribution."""
    ranked = sorted(factors, key=lambda f: abs(float(getattr(f, "contribution", 0.0) or 0.0)), reverse=True)
    out: list[dict[str, Any]] = []
    for factor in ranked[:limit]:
        out.append(
            {
                "factor_id": getattr(factor, "factor_id", ""),
                "display_name": getattr(factor, "display_name", ""),
                "contribution": round(float(getattr(factor, "contribution", 0.0) or 0.0), 2),
                "norm_score": round(float(getattr(factor, "norm_score", 0.0) or 0.0), 2),
                "weight": round(float(getattr(factor, "weight", 0.0) or 0.0), 4),
            }
        )
    return out


def build_factor_differences(
    legacy_signals: list[WeightedSignal] | None,
    engine_factors: list[Any],
) -> list[dict[str, Any]]:
    """Compare legacy signal scores vs engine factor norm scores by display name."""
    if not legacy_signals:
        return []
    legacy_by_name = {s.name.strip().lower(): s for s in legacy_signals}
    diffs: list[dict[str, Any]] = []
    for factor in engine_factors:
        display = str(getattr(factor, "display_name", "") or "").strip().lower()
        legacy = legacy_by_name.get(display)
        if legacy is None:
            continue
        engine_norm = float(getattr(factor, "norm_score", 0.0) or 0.0)
        legacy_norm = float(legacy.value)
        diffs.append(
            {
                "factor_id": getattr(factor, "factor_id", ""),
                "display_name": getattr(factor, "display_name", legacy.name),
                "legacy_norm_score": round(legacy_norm, 2),
                "engine_norm_score": round(engine_norm, 2),
                "norm_score_delta": round(abs(engine_norm - legacy_norm), 2),
                "legacy_contribution": round(float(legacy.contribution), 2),
                "engine_contribution": round(float(getattr(factor, "contribution", 0.0) or 0.0), 2),
            }
        )
    diffs.sort(key=lambda row: row["norm_score_delta"], reverse=True)
    return diffs[:TOP_FACTOR_CONTRIBUTION_COUNT]


def build_stage_b_parity_record(
    *,
    symbol: str,
    sleeve: str,
    legacy_score: float,
    engine_score: float,
    factors: list[Any],
    legacy_signals: list[WeightedSignal] | None = None,
    scoring_engine_used: bool = True,
    scan_id: str = "",
    scoring_version: str | None = None,
    timestamp: str | None = None,
) -> StageBParityRecord:
    legacy_bucket = recommendation_label_from_score(legacy_score)
    engine_bucket = recommendation_label_from_score(engine_score)
    delta = round(abs(legacy_score - engine_score), 2)
    ts = timestamp or datetime.now(timezone.utc).isoformat()
    return StageBParityRecord(
        symbol=symbol,
        sleeve=sleeve,
        legacy_score=round(legacy_score, 1),
        engine_score=round(engine_score, 1),
        parity_delta=delta,
        scoring_engine_used=scoring_engine_used,
        top_factor_contributions=top_factor_contributions(factors),
        legacy_recommendation_bucket=legacy_bucket,
        engine_recommendation_bucket=engine_bucket,
        recommendation_bucket_differs=legacy_bucket != engine_bucket,
        scan_id=scan_id,
        timestamp=ts,
        scoring_version=scoring_version or FACTOR_MODEL_VERSION,
        factor_differences=build_factor_differences(legacy_signals, factors),
    )


def aggregate_scan_parity_summary(
    records: list[StageBParityRecord],
    *,
    scoring_mode: str = "parity_sample",
    sample_rate: float | None = None,
) -> ScanParitySummary | None:
    if not records:
        return None
    deltas = [r.parity_delta for r in records]
    bucket_diffs = sum(1 for r in records if r.recommendation_bucket_differs)
    return ScanParitySummary(
        scoring_engine_used=all(r.scoring_engine_used for r in records),
        symbol_count=len(records),
        average_delta=round(sum(deltas) / len(deltas), 2),
        max_delta=round(max(deltas), 2),
        symbols_delta_gt_10=sum(1 for d in deltas if d > PARITY_DELTA_ALERT_THRESHOLD),
        recommendation_bucket_diffs=bucket_diffs,
        records=records,
        scoring_mode=scoring_mode,
        sample_rate=sample_rate,
    )


def log_stage_b_parity(record: StageBParityRecord) -> None:
    logger.info(
        "Scan score parity %s/%s legacy=%.1f engine=%.1f delta=%.1f "
        "legacy_bucket=%s engine_bucket=%s top_factors=%s factor_diffs=%d scan_id=%s",
        record.symbol,
        record.sleeve,
        record.legacy_score,
        record.engine_score,
        record.parity_delta,
        record.legacy_recommendation_bucket,
        record.engine_recommendation_bucket,
        record.top_factor_contributions,
        len(record.factor_differences),
        record.scan_id or "-",
    )


def log_scan_parity_summary(summary: ScanParitySummary, *, bucket: str) -> None:
    logger.info(
        "Scan parity summary bucket=%s mode=%s symbols=%d avg_delta=%.2f max_delta=%.2f "
        "delta_gt_10=%d recommendation_bucket_diffs=%d",
        bucket,
        summary.scoring_mode,
        summary.symbol_count,
        summary.average_delta,
        summary.max_delta,
        summary.symbols_delta_gt_10,
        summary.recommendation_bucket_diffs,
    )
