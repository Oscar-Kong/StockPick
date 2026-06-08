"""Data confidence score — wraps reconciler output for gating recommendations."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from config import DATA_CONFIDENCE_STRONG_BUY_MIN, DATA_CONFIDENCE_STRONG_REC_MIN
from data.reconciler import DataReconciler, ReconcileResult


@dataclass
class DataConfidence:
    score: float
    issues: list[str] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)
    field_flags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "data_confidence": round(self.score, 1),
            "issues": self.issues,
            "strengths": self.strengths,
            "field_flags": self.field_flags,
            "strong_recommendation_allowed": self.score >= DATA_CONFIDENCE_STRONG_REC_MIN,
            "strong_buy_allowed": self.score >= DATA_CONFIDENCE_STRONG_BUY_MIN,
        }


def build_data_confidence(symbol: str, rec: ReconcileResult | None = None) -> DataConfidence:
    rec = rec or DataReconciler().reconcile(symbol)
    issues: list[str] = []
    strengths: list[str] = []
    field_flags: list[str] = []

    if rec is None:
        return DataConfidence(score=0.0, issues=["No reconciliation data available"])

    for flag in rec.flags:
        issues.append(flag.replace("_", " "))

    for fld in rec.fields:
        if fld.confidence == "low":
            field_flags.append(f"{fld.field}: low confidence")
        elif fld.confidence == "high":
            strengths.append(f"{fld.field}: high confidence across sources")
        if fld.discarded:
            issues.append(f"{fld.field}: discarded sources {', '.join(fld.discarded)}")

    canonical = rec.canonical or {}
    if canonical.get("pe_ratio") is None:
        issues.append("P/E ratio missing")
    if canonical.get("revenue_ttm") is None:
        issues.append("Revenue data missing")
    else:
        strengths.append("Fundamentals reconciled")

    if canonical.get("price") is not None:
        strengths.append("Price data is adjusted correctly")

    score = float(rec.quality_score or 0.0)
    return DataConfidence(
        score=score,
        issues=issues[:12],
        strengths=strengths[:8],
        field_flags=field_flags[:12],
    )
