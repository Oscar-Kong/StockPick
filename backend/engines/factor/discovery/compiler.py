"""Non-executable compiler for Factor Discovery AST."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from models.schemas_factor_discovery import (
    AstNode,
    BinaryNode,
    ConditionalNode,
    ConstantNode,
    CrossSectionNode,
    CrossSectionOperator,
    FactorDefinition,
    FieldNode,
    NeutralizationKey,
    NeutralizeNode,
    RollingNode,
    RollingOperator,
    UnaryNode,
    ast_depth,
    collect_field_ids,
    formula_hash,
)
from models.schemas_factor_discovery import canonical_ast_payload

from .errors import (
    FactorCompileError,
    ForbiddenFieldError,
    InvalidOperatorArgumentsError,
    UnknownFieldError,
    UnsupportedNodeError,
)
from .field_registry import (
    FactorDataSourcePolicy,
    FactorFieldRegistry,
    FactorFieldSpec,
    FieldAvailability,
    default_data_source_policy,
)
from .formatter import format_factor_expression
from .limits import COMPILER_VERSION, FACTOR_DSL_V1, FactorCompileLimits


class CompiledFactorPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    dsl_version: str
    compiler_version: str
    canonical_ast: dict[str, Any]
    canonical_dsl: str
    formula_hash_value: str
    plan_hash_value: str
    required_field_ids: list[str]
    field_specs: list[FactorFieldSpec]
    max_lookback_sessions: int
    max_lag_sessions: int
    requires_cross_sectional: bool
    requires_time_series_history: bool
    requires_neutralization: bool
    neutralization_keys: list[str]
    requires_point_in_time_data: bool
    requires_publication_lag: bool
    min_publication_lag_by_field: dict[str, int]
    requires_adjusted_pricing: bool
    data_source_policy_id: str
    operators_used: list[str]
    ast_node_count: int
    ast_depth_value: int
    warnings: list[str] = Field(default_factory=list)
    unsupported_capabilities: list[str] = Field(default_factory=list)

    def plan_hash(self) -> str:
        return self.plan_hash_value


def _count_nodes(node: AstNode) -> int:
    if isinstance(node, FieldNode | ConstantNode):
        return 1
    if isinstance(node, UnaryNode | CrossSectionNode | NeutralizeNode):
        return 1 + _count_nodes(node.child)
    if isinstance(node, RollingNode):
        total = 1 + _count_nodes(node.child)
        if node.right is not None:
            total += _count_nodes(node.right)
        return total
    if isinstance(node, BinaryNode):
        return 1 + _count_nodes(node.left) + _count_nodes(node.right)
    if isinstance(node, ConditionalNode):
        return 1 + _count_nodes(node.condition) + _count_nodes(node.if_true) + _count_nodes(node.if_false)
    raise TypeError(type(node))


def _rolling_depth(node: AstNode) -> int:
    if isinstance(node, RollingNode):
        inner = _rolling_depth(node.child)
        if node.right is not None:
            inner = max(inner, _rolling_depth(node.right))
        return inner + 1
    if isinstance(node, UnaryNode | CrossSectionNode | NeutralizeNode):
        return _rolling_depth(node.child)
    if isinstance(node, BinaryNode):
        return max(_rolling_depth(node.left), _rolling_depth(node.right))
    if isinstance(node, ConditionalNode):
        return max(_rolling_depth(node.condition), _rolling_depth(node.if_true), _rolling_depth(node.if_false))
    return 0


def _lookback_sessions(node: AstNode) -> int:
    """Conservative session lookback: each lag/pct_change adds full window; rolling ops add full window."""
    if isinstance(node, FieldNode | ConstantNode):
        return 0
    if isinstance(node, UnaryNode | CrossSectionNode | NeutralizeNode):
        return _lookback_sessions(node.child)
    if isinstance(node, BinaryNode):
        return max(_lookback_sessions(node.left), _lookback_sessions(node.right))
    if isinstance(node, RollingNode):
        child_lb = _lookback_sessions(node.child)
        if node.op == RollingOperator.ROLLING_CORRELATION:
            right_lb = _lookback_sessions(node.right) if node.right is not None else 0
            return max(child_lb, right_lb) + node.window
        if node.op in {
            RollingOperator.LAG,
            RollingOperator.DELTA,
            RollingOperator.PCT_CHANGE,
            RollingOperator.ROLLING_MEAN,
            RollingOperator.ROLLING_STD,
            RollingOperator.ROLLING_MIN,
            RollingOperator.ROLLING_MAX,
            RollingOperator.ROLLING_SUM,
        }:
            return child_lb + node.window
        raise InvalidOperatorArgumentsError(
            code="unknown_rolling_op",
            message=f"unsupported rolling operator: {node.op.value}",
        )
    if isinstance(node, ConditionalNode):
        raise UnsupportedNodeError(
            code="conditional_unsupported",
            message="CONDITIONAL nodes are not supported in factor-dsl-v1 compilation",
        )
    raise TypeError(type(node))


def _max_lag_sessions(node: AstNode) -> int:
    if isinstance(node, RollingNode):
        child_lag = _max_lag_sessions(node.child)
        if node.right is not None:
            child_lag = max(child_lag, _max_lag_sessions(node.right))
        if node.op in {RollingOperator.LAG, RollingOperator.DELTA, RollingOperator.PCT_CHANGE}:
            return max(child_lag, node.window)
        return child_lag
    if isinstance(node, UnaryNode | CrossSectionNode | NeutralizeNode):
        return _max_lag_sessions(node.child)
    if isinstance(node, BinaryNode):
        return max(_max_lag_sessions(node.left), _max_lag_sessions(node.right))
    if isinstance(node, ConditionalNode):
        raise UnsupportedNodeError(
            code="conditional_unsupported",
            message="CONDITIONAL nodes are not supported in factor-dsl-v1 compilation",
        )
    return 0


def _collect_operators(node: AstNode, acc: set[str]) -> None:
    if isinstance(node, UnaryNode):
        acc.add(f"UNARY:{node.op.value}")
        _collect_operators(node.child, acc)
    elif isinstance(node, BinaryNode):
        acc.add(f"BINARY:{node.op.value}")
        _collect_operators(node.left, acc)
        _collect_operators(node.right, acc)
    elif isinstance(node, RollingNode):
        acc.add(f"ROLLING:{node.op.value}")
        _collect_operators(node.child, acc)
        if node.right is not None:
            _collect_operators(node.right, acc)
    elif isinstance(node, CrossSectionNode):
        acc.add(f"CROSS_SECTIONAL:{node.op.value}")
        _collect_operators(node.child, acc)
    elif isinstance(node, NeutralizeNode):
        acc.add(f"NEUTRALIZE:{node.key.value}")
        _collect_operators(node.child, acc)
    elif isinstance(node, ConditionalNode):
        acc.add("CONDITIONAL")
        _collect_operators(node.condition, acc)
        _collect_operators(node.if_true, acc)
        _collect_operators(node.if_false, acc)


def _has_cross_sectional(node: AstNode) -> bool:
    if isinstance(node, CrossSectionNode):
        return True
    if isinstance(node, UnaryNode | NeutralizeNode):
        return _has_cross_sectional(node.child)
    if isinstance(node, RollingNode):
        if _has_cross_sectional(node.child):
            return True
        return node.right is not None and _has_cross_sectional(node.right)
    if isinstance(node, BinaryNode):
        return _has_cross_sectional(node.left) or _has_cross_sectional(node.right)
    if isinstance(node, ConditionalNode):
        return (
            _has_cross_sectional(node.condition)
            or _has_cross_sectional(node.if_true)
            or _has_cross_sectional(node.if_false)
        )
    return False


def _has_rolling_or_field(node: AstNode) -> bool:
    if isinstance(node, FieldNode | RollingNode):
        return True
    if isinstance(node, UnaryNode | CrossSectionNode | NeutralizeNode):
        return _has_rolling_or_field(node.child)
    if isinstance(node, BinaryNode):
        return _has_rolling_or_field(node.left) or _has_rolling_or_field(node.right)
    if isinstance(node, ConditionalNode):
        return (
            _has_rolling_or_field(node.condition)
            or _has_rolling_or_field(node.if_true)
            or _has_rolling_or_field(node.if_false)
        )
    return False


def _collect_neutralization_keys(node: AstNode, acc: set[NeutralizationKey]) -> None:
    if isinstance(node, NeutralizeNode):
        acc.add(node.key)
        _collect_neutralization_keys(node.child, acc)
    elif isinstance(node, UnaryNode | CrossSectionNode):
        _collect_neutralization_keys(node.child, acc)
    elif isinstance(node, RollingNode):
        _collect_neutralization_keys(node.child, acc)
        if node.right is not None:
            _collect_neutralization_keys(node.right, acc)
    elif isinstance(node, BinaryNode):
        _collect_neutralization_keys(node.left, acc)
        _collect_neutralization_keys(node.right, acc)
    elif isinstance(node, ConditionalNode):
        _collect_neutralization_keys(node.condition, acc)
        _collect_neutralization_keys(node.if_true, acc)
        _collect_neutralization_keys(node.if_false, acc)


def _validate_fields(
    field_ids: frozenset[str],
    *,
    registry: FactorFieldRegistry,
    policy: FactorDataSourcePolicy,
) -> list[FactorFieldSpec]:
    specs: list[FactorFieldSpec] = []
    for field_id in sorted(field_ids):
        spec = registry.get(field_id)
        if spec is None:
            raise UnknownFieldError(
                code="unknown_field",
                message=f"unknown field: {field_id}",
                context=field_id,
            )
        if spec.is_outcome_label:
            raise ForbiddenFieldError(
                code="forbidden_outcome_field",
                message=f"outcome label fields cannot be used as factor inputs: {field_id}",
                context=field_id,
            )
        if spec.availability == FieldAvailability.UNAVAILABLE:
            raise FactorCompileError(
                code="unavailable_field",
                message=f"field is not available for compilation: {field_id}",
                context=field_id,
            )
        if not spec.factor_input_allowed:
            raise ForbiddenFieldError(
                code="forbidden_field",
                message=f"field is not permitted as a factor input: {field_id}",
                context=field_id,
            )
        if spec.field_id == "close" and policy.adjusted_prices_required:
            raise FactorCompileError(
                code="policy_incompatible_field",
                message=f"field {field_id} is incompatible with data-source policy {policy.policy_id}",
                context=field_id,
            )
        if spec.compatible_policy_ids and policy.policy_id not in spec.compatible_policy_ids:
            raise FactorCompileError(
                code="policy_incompatible_field",
                message=f"field {field_id} is incompatible with data-source policy {policy.policy_id}",
                context=field_id,
            )
        specs.append(spec)
    return specs


def _plan_hash(
    *,
    formula_hash_value: str,
    registry_version: str,
    policy_id: str,
    compiler_version: str,
    required_field_ids: list[str],
) -> str:
    payload = {
        "formula_hash": formula_hash_value,
        "registry_version": registry_version,
        "data_source_policy_id": policy_id,
        "compiler_version": compiler_version,
        "required_field_ids": required_field_ids,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return f"sha256:{hashlib.sha256(canonical.encode('utf-8')).hexdigest()}"


def compile_factor_expression(
    expression: AstNode,
    *,
    field_registry: FactorFieldRegistry,
    data_source_policy: FactorDataSourcePolicy | None = None,
    dsl_version: str = FACTOR_DSL_V1,
    limits: FactorCompileLimits | None = None,
) -> CompiledFactorPlan:
    """Compile a validated AST into a deterministic non-executable plan."""
    if dsl_version != FACTOR_DSL_V1:
        raise FactorCompileError(
            code="unsupported_dsl_version",
            message=f"unsupported DSL version: {dsl_version}",
        )
    lim = limits or FactorCompileLimits()
    policy = data_source_policy or default_data_source_policy()

    if isinstance(expression, ConditionalNode):
        raise UnsupportedNodeError(
            code="conditional_unsupported",
            message="CONDITIONAL nodes are not supported in factor-dsl-v1 compilation",
        )

    depth = ast_depth(expression)
    node_count = _count_nodes(expression)
    if depth > lim.max_ast_depth:
        raise FactorCompileError(code="ast_too_deep", message=f"AST depth {depth} exceeds limit {lim.max_ast_depth}")
    if node_count > lim.max_ast_nodes:
        raise FactorCompileError(code="too_many_nodes", message=f"AST node count {node_count} exceeds limit {lim.max_ast_nodes}")

    field_ids = collect_field_ids(expression)
    if len(field_ids) > lim.max_distinct_fields:
        raise FactorCompileError(
            code="too_many_fields",
            message=f"distinct field count {len(field_ids)} exceeds limit {lim.max_distinct_fields}",
        )

    lookback = _lookback_sessions(expression)
    if lookback > lim.max_total_lookback:
        raise FactorCompileError(
            code="lookback_too_large",
            message=f"required lookback {lookback} exceeds limit {lim.max_total_lookback}",
        )

    rolling_depth = _rolling_depth(expression)
    if rolling_depth > lim.max_nested_rolling_depth:
        raise FactorCompileError(
            code="rolling_nesting_too_deep",
            message=f"nested rolling depth {rolling_depth} exceeds limit {lim.max_nested_rolling_depth}",
        )

    specs = _validate_fields(field_ids, registry=field_registry, policy=policy)
    required_field_ids = sorted(field_ids)

    neutral_keys: set[NeutralizationKey] = set()
    _collect_neutralization_keys(expression, neutral_keys)

    min_pub_lag = {
        s.field_id: s.min_publication_lag_sessions
        for s in specs
        if s.requires_publication_lag and s.min_publication_lag_sessions > 0
    }

    requires_pit = any(s.requires_point_in_time for s in specs)
    requires_pub_lag = any(s.requires_publication_lag for s in specs)
    requires_adjusted = policy.adjusted_prices_required or any(s.requires_adjusted_price for s in specs)

    operators: set[str] = set()
    _collect_operators(expression, operators)

    warnings: list[str] = []
    for s in specs:
        if s.availability == FieldAvailability.DERIVED_PANEL:
            warnings.append(f"field {s.field_id} uses derived panel data; Phase 3 must materialize from pinned sources")

    fh = formula_hash(expression)
    canonical_dsl = format_factor_expression(expression)
    plan_hash_value = _plan_hash(
        formula_hash_value=fh,
        registry_version=field_registry.version,
        policy_id=policy.policy_id,
        compiler_version=COMPILER_VERSION,
        required_field_ids=required_field_ids,
    )

    return CompiledFactorPlan(
        dsl_version=dsl_version,
        compiler_version=COMPILER_VERSION,
        canonical_ast=canonical_ast_payload(expression),
        canonical_dsl=canonical_dsl,
        formula_hash_value=fh,
        plan_hash_value=plan_hash_value,
        required_field_ids=required_field_ids,
        field_specs=specs,
        max_lookback_sessions=lookback,
        max_lag_sessions=_max_lag_sessions(expression),
        requires_cross_sectional=_has_cross_sectional(expression),
        requires_time_series_history=_has_rolling_or_field(expression),
        requires_neutralization=bool(neutral_keys),
        neutralization_keys=sorted(k.value for k in neutral_keys),
        requires_point_in_time_data=requires_pit,
        requires_publication_lag=requires_pub_lag,
        min_publication_lag_by_field=min_pub_lag,
        requires_adjusted_pricing=requires_adjusted,
        data_source_policy_id=policy.policy_id,
        operators_used=sorted(operators),
        ast_node_count=node_count,
        ast_depth_value=depth,
        warnings=sorted(set(warnings)),
        unsupported_capabilities=["CONDITIONAL"],
    )


def compile_factor_definition(
    definition: FactorDefinition,
    *,
    field_registry: FactorFieldRegistry,
    data_source_policy: FactorDataSourcePolicy | None = None,
) -> CompiledFactorPlan:
    """Compile a FactorDefinition after verifying declared metadata."""
    derived = sorted(collect_field_ids(definition.expression))
    if definition.required_fields and sorted(definition.required_fields) != derived:
        raise FactorCompileError(
            code="required_fields_mismatch",
            message=(
                f"required_fields {sorted(definition.required_fields)} "
                f"does not match AST fields {derived}"
            ),
        )
    policy = data_source_policy or default_data_source_policy()
    if definition.data_source_policy_id != policy.policy_id:
        raise FactorCompileError(
            code="policy_mismatch",
            message=(
                f"definition data_source_policy_id {definition.data_source_policy_id!r} "
                f"does not match compilation policy {policy.policy_id!r}"
            ),
        )
    expected_hash = definition.formula_hash()
    plan = compile_factor_expression(
        definition.expression,
        field_registry=field_registry,
        data_source_policy=policy,
    )
    if plan.formula_hash_value != expected_hash:
        raise FactorCompileError(
            code="formula_hash_mismatch",
            message="definition formula_hash does not match expression",
        )
    return plan
