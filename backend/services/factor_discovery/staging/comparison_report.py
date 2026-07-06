"""Repeat-run comparison report for staging."""
from __future__ import annotations

import json
from dataclasses import dataclass, field


@dataclass
class StagingRunComparison:
    run_id_a: str
    run_id_b: str
    snapshot_id: str | None = None
    formula_hash_a: str | None = None
    formula_hash_b: str | None = None
    artifact_hash_a: str | None = None
    artifact_hash_b: str | None = None
    metric_differences: dict = field(default_factory=dict)
    expected_differences: list[str] = field(default_factory=list)
    unexpected_differences: list[str] = field(default_factory=list)
    status: str = "NOT_COMPARABLE"

    def to_dict(self) -> dict:
        return {
            "run_id_a": self.run_id_a,
            "run_id_b": self.run_id_b,
            "snapshot_id": self.snapshot_id,
            "formula_hash_a": self.formula_hash_a,
            "formula_hash_b": self.formula_hash_b,
            "artifact_hash_a": self.artifact_hash_a,
            "artifact_hash_b": self.artifact_hash_b,
            "metric_differences": self.metric_differences,
            "expected_differences": self.expected_differences,
            "unexpected_differences": self.unexpected_differences,
            "status": self.status,
        }


class FactorDiscoveryStagingComparisonService:
    def compare_runs(
        self,
        *,
        run_a: dict,
        run_b: dict,
        allow_family_context_diff: bool = False,
    ) -> StagingRunComparison:
        cmp = StagingRunComparison(
            run_id_a=str(run_a.get("run_id")),
            run_id_b=str(run_b.get("run_id")),
            snapshot_id=run_a.get("snapshot_id") or run_b.get("snapshot_id"),
            formula_hash_a=run_a.get("formula_hash"),
            formula_hash_b=run_b.get("formula_hash"),
            artifact_hash_a=run_a.get("artifact_hash"),
            artifact_hash_b=run_b.get("artifact_hash"),
        )
        if cmp.formula_hash_a != cmp.formula_hash_b or run_a.get("snapshot_id") != run_b.get("snapshot_id"):
            cmp.status = "NOT_COMPARABLE"
            cmp.unexpected_differences.append("different_factor_or_snapshot")
            return cmp

        metrics_a = run_a.get("metrics") or {}
        metrics_b = run_b.get("metrics") or {}
        for key in sorted(set(metrics_a) | set(metrics_b)):
            if metrics_a.get(key) != metrics_b.get(key):
                cmp.metric_differences[key] = {"a": metrics_a.get(key), "b": metrics_b.get(key)}

        mt_a = run_a.get("multiple_testing_context")
        mt_b = run_b.get("multiple_testing_context")
        if mt_a != mt_b:
            if allow_family_context_diff:
                cmp.expected_differences.append("multiple_testing_context")
            else:
                cmp.unexpected_differences.append("multiple_testing_context")

        if cmp.artifact_hash_a == cmp.artifact_hash_b and not cmp.metric_differences:
            cmp.status = "EXACT_MATCH"
        elif cmp.artifact_hash_a == cmp.artifact_hash_b and cmp.expected_differences and not cmp.unexpected_differences:
            cmp.status = "SEMANTIC_MATCH_WITH_EXPECTED_CONTEXT_DIFFERENCE"
        elif cmp.unexpected_differences or cmp.metric_differences:
            cmp.status = "MISMATCH"
        else:
            cmp.status = "EXACT_MATCH"
        return cmp
