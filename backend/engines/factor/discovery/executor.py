"""Deterministic Factor Discovery panel executor."""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from pydantic import TypeAdapter

from engines.factor.discovery.compiler import CompiledFactorPlan
from engines.factor.discovery.cross_sectional import (
    apply_percentile_rank,
    apply_rank,
    apply_winsorize,
    apply_zscore,
)
from engines.factor.discovery.errors import UnsupportedNodeError
from engines.factor.discovery.execution_errors import OperatorExecutionError, PanelLimitError
from engines.factor.discovery.field_resolver import ResolvedFieldBundle, resolve_fields
from engines.factor.discovery.neutralization import neutralize_industry, neutralize_market_cap, neutralize_sector
from engines.factor.discovery.operators import (
    ExecutionContext,
    apply_abs,
    apply_add,
    apply_delta,
    apply_divide,
    apply_lag,
    apply_log,
    apply_max,
    apply_min,
    apply_multiply,
    apply_negate,
    apply_pct_change,
    apply_rolling_correlation,
    apply_rolling_max,
    apply_rolling_mean,
    apply_rolling_min,
    apply_rolling_std,
    apply_rolling_sum,
    apply_sign,
    apply_subtract,
    sanitize_series,
)
from engines.factor.discovery.panel_models import (
    FactorExecutionConfig,
    FactorExecutionLimits,
    FactorExecutionResult,
    FactorInputPanel,
    OperatorDiagnostics,
    validate_input_panel,
)
from engines.factor.discovery.provenance import PanelFieldSourceType
from engines.factor.discovery.sessions import align_panel_to_canonical_sessions
from engines.factor.discovery.result_hashing import EXECUTOR_VERSION, execution_hash
from models.schemas_factor_discovery import (
    AstNode,
    BinaryNode,
    ConditionalNode,
    ConstantNode,
    CrossSectionNode,
    CrossSectionOperator,
    FieldNode,
    NeutralizationKey,
    NeutralizeNode,
    RollingNode,
    RollingOperator,
    UnaryNode,
)

_AST_ADAPTER = TypeAdapter(AstNode)


def _ast_from_plan(plan: CompiledFactorPlan) -> AstNode:
    return _AST_ADAPTER.validate_python(plan.canonical_ast)


def _estimate_operations(plan: CompiledFactorPlan, row_count: int) -> int:
    return plan.ast_node_count * row_count


class _Evaluator:
    def __init__(
        self,
        *,
        plan: CompiledFactorPlan,
        panel: FactorInputPanel,
        fields: ResolvedFieldBundle,
        config: FactorExecutionConfig,
    ) -> None:
        self.plan = plan
        self.panel = panel
        self.fields = fields
        self.config = config
        self.eligibility = panel.eligibility.astype(bool)
        self.ctx = ExecutionContext(index=panel.frame.index, config=config)
        self.neutralization_diagnostics: list = []

    def evaluate(self, node: AstNode) -> pd.Series:
        if isinstance(node, FieldNode):
            if node.field_id not in self.fields.series:
                raise OperatorExecutionError(
                    code="missing_resolved_field",
                    message=f"field not resolved: {node.field_id}",
                    context=node.field_id,
                )
            return self.fields.series[node.field_id].reindex(self.ctx.index)

        if isinstance(node, ConstantNode):
            return pd.Series(float(node.value), index=self.ctx.index)

        if isinstance(node, UnaryNode):
            child = sanitize_series(self.evaluate(node.child), self.ctx)
            if node.op.value == "ABS":
                return sanitize_series(apply_abs(child, self.ctx), self.ctx)
            if node.op.value == "NEGATE":
                return sanitize_series(apply_negate(child, self.ctx), self.ctx)
            if node.op.value == "LOG":
                return sanitize_series(apply_log(child, self.ctx, node.log_policy), self.ctx)
            if node.op.value == "SIGN":
                return sanitize_series(apply_sign(child, self.ctx), self.ctx)
            raise OperatorExecutionError(code="unknown_unary", message=f"unknown unary op: {node.op}")

        if isinstance(node, BinaryNode):
            left = sanitize_series(self.evaluate(node.left), self.ctx)
            right = sanitize_series(self.evaluate(node.right), self.ctx)
            op = node.op.value
            if op == "ADD":
                return sanitize_series(apply_add(left, right, self.ctx), self.ctx)
            if op == "SUBTRACT":
                return sanitize_series(apply_subtract(left, right, self.ctx), self.ctx)
            if op == "MULTIPLY":
                return sanitize_series(apply_multiply(left, right, self.ctx), self.ctx)
            if op == "DIVIDE":
                return sanitize_series(apply_divide(left, right, self.ctx, node.zero_policy), self.ctx)
            if op == "MIN":
                return sanitize_series(apply_min(left, right, self.ctx), self.ctx)
            if op == "MAX":
                return sanitize_series(apply_max(left, right, self.ctx), self.ctx)
            raise OperatorExecutionError(code="unknown_binary", message=f"unknown binary op: {node.op}")

        if isinstance(node, RollingNode):
            if node.op == RollingOperator.ROLLING_CORRELATION:
                left = sanitize_series(self.evaluate(node.child), self.ctx)
                right = sanitize_series(self.evaluate(node.right), self.ctx) if node.right else None
                if right is None:
                    raise OperatorExecutionError(code="missing_right", message="rolling correlation missing right")
                return sanitize_series(apply_rolling_correlation(left, right, node.window, self.ctx), self.ctx)
            child = sanitize_series(self.evaluate(node.child), self.ctx)
            op = node.op
            if op == RollingOperator.LAG:
                return sanitize_series(apply_lag(child, node.window, self.ctx), self.ctx)
            if op == RollingOperator.DELTA:
                return sanitize_series(apply_delta(child, node.window, self.ctx), self.ctx)
            if op == RollingOperator.PCT_CHANGE:
                return sanitize_series(apply_pct_change(child, node.window, self.ctx), self.ctx)
            if op == RollingOperator.ROLLING_MEAN:
                return sanitize_series(apply_rolling_mean(child, node.window, self.ctx), self.ctx)
            if op == RollingOperator.ROLLING_STD:
                return sanitize_series(apply_rolling_std(child, node.window, self.ctx), self.ctx)
            if op == RollingOperator.ROLLING_MIN:
                return sanitize_series(apply_rolling_min(child, node.window, self.ctx), self.ctx)
            if op == RollingOperator.ROLLING_MAX:
                return sanitize_series(apply_rolling_max(child, node.window, self.ctx), self.ctx)
            if op == RollingOperator.ROLLING_SUM:
                return sanitize_series(apply_rolling_sum(child, node.window, self.ctx), self.ctx)
            raise OperatorExecutionError(code="unknown_rolling", message=f"unknown rolling op: {op}")

        if isinstance(node, CrossSectionNode):
            child = sanitize_series(self.evaluate(node.child), self.ctx)
            diag = self.ctx.diagnostics
            if node.op == CrossSectionOperator.RANK:
                return sanitize_series(apply_rank(child, self.eligibility, self.config, diag), self.ctx)
            if node.op == CrossSectionOperator.PERCENTILE_RANK:
                return sanitize_series(apply_percentile_rank(child, self.eligibility, self.config, diag), self.ctx)
            if node.op == CrossSectionOperator.ZSCORE:
                return sanitize_series(apply_zscore(child, self.eligibility, self.config, diag), self.ctx)
            if node.op == CrossSectionOperator.WINSORIZE:
                return sanitize_series(
                    apply_winsorize(
                        child,
                        self.eligibility,
                        node.winsorize_lower,
                        node.winsorize_upper,
                        self.config,
                        diag,
                    ),
                    self.ctx,
                )
            raise OperatorExecutionError(code="unknown_cross_section", message=f"unknown cross-section op: {node.op}")

        if isinstance(node, NeutralizeNode):
            child = sanitize_series(self.evaluate(node.child), self.ctx)
            if node.key == NeutralizationKey.SECTOR:
                sector = self.panel.frame.get("sector")
                if sector is None:
                    sector = self.fields.series.get("sector")
                out, nd = neutralize_sector(child, sector, self.config)
                self.neutralization_diagnostics.append(nd)
                return sanitize_series(out, self.ctx)
            if node.key == NeutralizationKey.INDUSTRY:
                industry = self.panel.frame.get("industry")
                if industry is None:
                    industry = self.fields.series.get("industry")
                out, nd = neutralize_industry(child, industry, self.config)
                self.neutralization_diagnostics.append(nd)
                return sanitize_series(out, self.ctx)
            if node.key == NeutralizationKey.MARKET_CAP:
                mc = self.fields.series.get("market_cap")
                if mc is None and "market_cap" in self.panel.frame.columns:
                    mc = self.panel.frame["market_cap"]
                out, nd = neutralize_market_cap(child, mc, self.eligibility, self.config)
                self.neutralization_diagnostics.append(nd)
                return sanitize_series(out, self.ctx)
            raise OperatorExecutionError(code="unknown_neutralize", message=f"unknown neutralization: {node.key}")

        if isinstance(node, ConditionalNode):
            raise UnsupportedNodeError(
                code="conditional_unsupported",
                message="CONDITIONAL nodes are not supported in execution",
            )

        raise OperatorExecutionError(code="unknown_node", message=f"unknown AST node: {type(node)}")


def compute_factor_panel(
    plan: CompiledFactorPlan,
    panel: FactorInputPanel,
    *,
    execution_config: FactorExecutionConfig | None = None,
    limits: FactorExecutionLimits | None = None,
) -> FactorExecutionResult:
    """Execute a compiled factor plan against a supplied panel."""
    config = execution_config or FactorExecutionConfig()
    lim = limits or FactorExecutionLimits()
    panel, _calendar, missing_session_rows = align_panel_to_canonical_sessions(panel)
    validate_input_panel(panel, plan=plan, limits=lim)

    est_ops = _estimate_operations(plan, panel.row_count)
    if est_ops > lim.max_estimated_operations:
        raise PanelLimitError(
            code="too_many_operations",
            message=f"estimated operations {est_ops} exceed limit {lim.max_estimated_operations}",
        )

    fields = resolve_fields(plan, panel, config=config)
    evaluator = _Evaluator(plan=plan, panel=panel, fields=fields, config=config)
    ast = _ast_from_plan(plan)
    factor_values = evaluator.evaluate(ast)
    factor_values = sanitize_series(factor_values, evaluator.ctx)
    factor_values = factor_values.where(panel.eligibility.astype(bool))

    valid_mask = factor_values.notna()
    valid_count = int(valid_mask.sum())
    missing_count = int((~valid_mask).sum())
    coverage = 100.0 * valid_count / panel.row_count if panel.row_count else 0.0

    coverage_by_date: dict[str, float] = {}
    for dt, grp in valid_mask.groupby(level="date"):
        coverage_by_date[str(pd.Timestamp(dt).date())] = round(100.0 * float(grp.mean()), 4)

    coverage_by_symbol: dict[str, float] = {}
    for sym, grp in valid_mask.groupby(level="symbol"):
        coverage_by_symbol[str(sym)] = round(100.0 * float(grp.mean()), 4)

    exec_hash = execution_hash(
        plan_hash_value=plan.plan_hash_value,
        panel_content_hash=panel.content_hash,
        config=config,
    )

    derived_prov = [
        p for p in fields.provenance.values() if p.source_type == PanelFieldSourceType.DERIVED
    ]
    primitive_prov = [
        p for p in fields.provenance.values() if p.source_type != PanelFieldSourceType.DERIVED
    ]

    warnings: list[str] = []
    if missing_session_rows > 0:
        warnings.append(f"canonical session alignment: {missing_session_rows} missing (date,symbol) rows")
    if panel.symbol_count == 1 and plan.requires_cross_sectional:
        warnings.append("single-symbol panel: cross-sectional operations are not meaningful")

    return FactorExecutionResult(
        formula_hash_value=plan.formula_hash_value,
        plan_hash_value=plan.plan_hash_value,
        execution_hash_value=exec_hash,
        executor_version=EXECUTOR_VERSION,
        panel_content_hash=panel.content_hash,
        data_source_policy_id=panel.data_source_policy_id,
        provider_id=panel.provider_id,
        factor_values=factor_values,
        valid_mask=valid_mask,
        eligibility_mask=panel.eligibility.astype(bool),
        start_date=panel.start_date,
        end_date=panel.end_date,
        symbol_count=panel.symbol_count,
        date_count=panel.date_count,
        row_count=panel.row_count,
        valid_output_count=valid_count,
        missing_output_count=missing_count,
        coverage_pct=round(coverage, 4),
        coverage_by_date=coverage_by_date,
        coverage_by_symbol=coverage_by_symbol,
        field_provenance=primitive_prov,
        derived_field_provenance=derived_prov,
        operator_diagnostics=evaluator.ctx.diagnostics.to_model(),
        neutralization_diagnostics=evaluator.neutralization_diagnostics,
        warnings=warnings,
        determinism_metadata={
            "executor_version": EXECUTOR_VERSION,
            "config_version": config.config_version,
        },
    )
