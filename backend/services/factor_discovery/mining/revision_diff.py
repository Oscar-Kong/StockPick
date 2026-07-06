"""AST revision diff and policy validation."""
from __future__ import annotations

from dataclasses import dataclass

from models.schemas_factor_discovery import AstNode, collect_field_ids, formula_hash
from services.factor_discovery.mining.errors import MiningRevisionPolicyError
from services.factor_discovery.mining.models import FactorMiningBudgetPolicy


@dataclass(frozen=True)
class RevisionDiffResult:
    parent_formula_hash: str
    child_formula_hash: str
    fields_added: tuple[str, ...]
    fields_removed: tuple[str, ...]
    operator_changes: int
    lookback_changes: int
    depth_delta: int
    node_delta: int
    semantic_classification: str


def _ast_depth(node: AstNode, depth: int = 1) -> int:
    children = []
    if hasattr(node, "child") and node.child is not None:
        children.append(node.child)
    if hasattr(node, "left") and node.left is not None:
        children.append(node.left)
    if hasattr(node, "right") and node.right is not None:
        children.append(node.right)
    if not children:
        return depth
    return max(_ast_depth(c, depth + 1) for c in children)


def _count_nodes(node: AstNode) -> int:
    total = 1
    for attr in ("child", "left", "right"):
        child = getattr(node, attr, None)
        if child is not None:
            total += _count_nodes(child)
    return total


def diff_revision(parent_ast: AstNode, child_ast: AstNode) -> RevisionDiffResult:
    parent_fields = collect_field_ids(parent_ast)
    child_fields = collect_field_ids(child_ast)
    added = tuple(sorted(child_fields - parent_fields))
    removed = tuple(sorted(parent_fields - child_fields))
    parent_depth = _ast_depth(parent_ast)
    child_depth = _ast_depth(child_ast)
    parent_nodes = _count_nodes(parent_ast)
    child_nodes = _count_nodes(child_ast)
    classification = "minor_tweak"
    if added or removed:
        classification = "field_change"
    if child_depth - parent_depth > 1 or child_nodes - parent_nodes > 3:
        classification = "major_restructure"
    return RevisionDiffResult(
        parent_formula_hash=formula_hash(parent_ast),
        child_formula_hash=formula_hash(child_ast),
        fields_added=added,
        fields_removed=removed,
        operator_changes=abs(child_nodes - parent_nodes),
        lookback_changes=0,
        depth_delta=child_depth - parent_depth,
        node_delta=child_nodes - parent_nodes,
        semantic_classification=classification,
    )


def validate_revision_policy(
    diff: RevisionDiffResult,
    *,
    budget: FactorMiningBudgetPolicy,
    evaluated_hashes: set[str],
) -> None:
    if diff.child_formula_hash == diff.parent_formula_hash:
        raise MiningRevisionPolicyError("REVISION_IDENTICAL", diff.child_formula_hash)
    if diff.child_formula_hash in evaluated_hashes:
        raise MiningRevisionPolicyError("REVISION_CYCLE", diff.child_formula_hash)
    if len(diff.fields_added) > 1 or len(diff.fields_removed) > 1:
        raise MiningRevisionPolicyError("REVISION_TOO_MANY_FIELD_CHANGES", str(diff.fields_added))
    if diff.depth_delta > 1:
        raise MiningRevisionPolicyError("REVISION_DEPTH_EXCEEDED", str(diff.depth_delta))
    if diff.node_delta > budget.max_ast_nodes // 4:
        raise MiningRevisionPolicyError("REVISION_NODE_INCREASE", str(diff.node_delta))
