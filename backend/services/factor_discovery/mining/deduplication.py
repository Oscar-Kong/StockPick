"""Formula deduplication for mining sessions."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from models.schemas_factor_discovery import AstNode, collect_field_ids, formula_hash
from services.factor_discovery.mining.repositories import FactorMiningEvaluationRepository
from services.factor_discovery.repositories import FactorDefinitionRepository


@dataclass(frozen=True)
class DuplicateCheckResult:
    is_duplicate: bool
    reason: str | None = None
    existing_evaluation_id: str | None = None
    existing_artifact_id: str | None = None


def structural_fingerprint(ast: AstNode) -> str:
    payload = {
        "formula_hash": formula_hash(ast),
        "fields": sorted(collect_field_ids(ast)),
        "shape": _shape_signature(ast),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return f"sha256:{hashlib.sha256(canonical.encode()).hexdigest()}"


def _shape_signature(node: AstNode) -> str:
    from pydantic import TypeAdapter

    from models.schemas_factor_discovery import AstNode as AstNodeType

    adapter = TypeAdapter(AstNodeType)
    data = node.model_dump(mode="json")
    kind = data.get("kind", "")
    parts = [kind]
    for key in sorted(data.keys()):
        if key in {"kind", "field_id", "op", "window", "zero_policy"}:
            parts.append(f"{key}={data[key]}")
    for child_key in ("child", "right", "left"):
        child = data.get(child_key)
        if child:
            parts.append(_shape_signature(adapter.validate_python(child)))
    return "|".join(parts)


class MiningDeduplicationService:
    def __init__(self) -> None:
        self._evaluations = FactorMiningEvaluationRepository()
        self._definitions = FactorDefinitionRepository()

    def check_formula_hash(
        self,
        *,
        session_id: str,
        lineage_id: str,
        formula_hash_value: str,
        revision_round: int = 0,
    ) -> DuplicateCheckResult:
        existing = self._evaluations.get_by_formula(
            session_id, lineage_id, formula_hash_value, revision_round=revision_round
        )
        if existing:
            return DuplicateCheckResult(
                is_duplicate=True,
                reason="session_lineage_formula_hash",
                existing_evaluation_id=existing.evaluation_id,
                existing_artifact_id=existing.artifact_id,
            )
        return DuplicateCheckResult(is_duplicate=False)

    def check_family_definition(self, formula_hash_value: str) -> DuplicateCheckResult:
        return DuplicateCheckResult(is_duplicate=False)
