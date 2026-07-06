"""Deterministic candidate queue priority for mining sessions."""
from __future__ import annotations

from services.factor_discovery.mining.models import QUEUE_PRIORITY_VERSION
from services.research_json import json_dumps


def compute_queue_priority(
    *,
    executable: bool,
    formula_simplicity: int,
    revision_depth: int,
    structural_duplicate_penalty: int = 0,
    human_priority: int = 0,
    provider_compatible: bool = True,
    lineage_status: str,
    creation_order: int,
) -> dict:
    score = human_priority * 1000
    score += 100 if executable else 0
    score += max(0, 50 - formula_simplicity)
    score -= revision_depth * 10
    score -= structural_duplicate_penalty * 25
    score += 20 if provider_compatible else -100
    score -= creation_order
    return {
        "schema_version": QUEUE_PRIORITY_VERSION,
        "score": score,
        "components": {
            "human_priority": human_priority,
            "executable": executable,
            "formula_simplicity": formula_simplicity,
            "revision_depth": revision_depth,
            "structural_duplicate_penalty": structural_duplicate_penalty,
            "provider_compatible": provider_compatible,
            "lineage_status": lineage_status,
            "creation_order": creation_order,
        },
    }


def priority_json(**kwargs) -> str:
    return json_dumps(compute_queue_priority(**kwargs))
