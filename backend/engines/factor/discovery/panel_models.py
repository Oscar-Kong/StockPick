"""Input panel and execution configuration contracts."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from engines.factor.discovery.compiler import CompiledFactorPlan
from engines.factor.discovery.execution_errors import (
    AdjustedPriceViolationError,
    InvalidInputPanelError,
    PanelLimitError,
    PanelPolicyMismatchError,
    UniverseEvidenceError,
)
from engines.factor.discovery.field_registry import build_default_field_registry
from engines.factor.discovery.provenance import PanelFieldProvenance, PitProvenanceState

FORBIDDEN_PANEL_FIELDS = frozenset(
    {
        "forward_return_5d",
        "forward_return_21d",
        "future_return",
        "target_return",
    }
)


class FactorExecutionLimits(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    max_rows: int = 5_000_000
    max_symbols: int = 10_000
    max_dates: int = 50_000
    max_estimated_operations: int = 50_000_000


class FactorExecutionConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    min_cross_sectional_observations: int = 2
    min_neutralization_group_size: int = 2
    missing_value_output: str = "nan"
    zero_variance_zscore: str = "nan"
    rank_tie_method: str = "average"
    percentile_rank_endpoint: str = "inclusive_0_1"
    rolling_min_periods_policy: str = "full_window"
    rolling_std_ddof: int = 1
    pct_change_zero_prior: str = "nan"
    strict_pit_mode: bool = True
    warnings_fatal: bool = False
    config_version: str = "factor-execution-config-v1"

    def canonical_payload(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


@dataclass(frozen=True)
class FactorInputPanel:
    """Supplied historical research panel; caller owns data sourcing."""

    frame: pd.DataFrame
    eligibility: pd.Series
    data_source_policy_id: str
    provider_id: str
    prices_adjusted: bool
    field_provenance: dict[str, PanelFieldProvenance]
    panel_version: str = "factor-panel-v1"
    timezone: str = "UTC"
    has_universe_membership: bool = True

    @property
    def content_hash(self) -> str:
        from engines.factor.discovery.result_hashing import hash_panel_content

        return hash_panel_content(
            self.frame,
            eligibility=self.eligibility,
            data_source_policy_id=self.data_source_policy_id,
            provider_id=self.provider_id,
            prices_adjusted=self.prices_adjusted,
            field_provenance=self.field_provenance,
            panel_version=self.panel_version,
        )

    @property
    def start_date(self) -> date:
        idx = self.frame.index
        return pd.Timestamp(idx.get_level_values(0).min()).date()

    @property
    def end_date(self) -> date:
        idx = self.frame.index
        return pd.Timestamp(idx.get_level_values(0).max()).date()

    @property
    def symbol_count(self) -> int:
        return int(self.frame.index.get_level_values(1).nunique())

    @property
    def date_count(self) -> int:
        return int(self.frame.index.get_level_values(0).nunique())

    @property
    def row_count(self) -> int:
        return int(len(self.frame))


def _ensure_multiindex(frame: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(frame.index, pd.MultiIndex):
        raise InvalidInputPanelError(
            code="invalid_index",
            message="panel index must be a MultiIndex of (date, symbol)",
        )
    if frame.index.nlevels != 2:
        raise InvalidInputPanelError(
            code="invalid_index_levels",
            message="panel index must have exactly two levels: date, symbol",
        )
    names = list(frame.index.names)
    if names[0] is None:
        names[0] = "date"
    if names[1] is None:
        names[1] = "symbol"
    frame = frame.copy()
    frame.index = frame.index.set_names(names)
    return frame.sort_index()


def validate_input_panel(
    panel: FactorInputPanel,
    *,
    plan: CompiledFactorPlan | None = None,
    limits: FactorExecutionLimits | None = None,
) -> None:
    """Validate panel contract; raise typed errors on violation."""
    lim = limits or FactorExecutionLimits()
    frame = _ensure_multiindex(panel.frame)

    if frame.empty:
        raise InvalidInputPanelError(code="empty_panel", message="panel contains no rows")

    if frame.index.duplicated().any():
        raise InvalidInputPanelError(code="duplicate_index", message="duplicate (date, symbol) rows")

    if len(frame.columns) != len(set(frame.columns)):
        raise InvalidInputPanelError(code="duplicate_fields", message="duplicate field columns")

    for forbidden in FORBIDDEN_PANEL_FIELDS:
        if forbidden in frame.columns:
            raise InvalidInputPanelError(
                code="forbidden_outcome_field",
                message=f"outcome field cannot be supplied as factor input: {forbidden}",
                context=forbidden,
            )

    if not panel.has_universe_membership:
        raise UniverseEvidenceError(
            code="missing_universe_evidence",
            message="panel must include explicit universe membership (eligibility mask)",
        )

    if not isinstance(panel.eligibility, pd.Series):
        raise InvalidInputPanelError(code="invalid_eligibility", message="eligibility must be a Series")
    if not panel.eligibility.index.equals(frame.index):
        raise InvalidInputPanelError(
            code="eligibility_index_mismatch",
            message="eligibility index must match panel frame index",
        )

    for col in frame.columns:
        series = frame[col]
        if series.dtype == bool:
            raise InvalidInputPanelError(
                code="boolean_field",
                message=f"boolean column cannot be used as numeric factor field: {col}",
                context=col,
            )
        arr = pd.to_numeric(series, errors="coerce")
        if np.isinf(arr.to_numpy(dtype=float, copy=False)).any():
            raise InvalidInputPanelError(
                code="non_finite_values",
                message=f"non-finite values in column: {col}",
                context=col,
            )

    if panel.row_count > lim.max_rows:
        raise PanelLimitError(code="too_many_rows", message=f"panel rows {panel.row_count} exceed limit")
    if panel.symbol_count > lim.max_symbols:
        raise PanelLimitError(code="too_many_symbols", message=f"symbol count exceeds limit")
    if panel.date_count > lim.max_dates:
        raise PanelLimitError(code="too_many_dates", message=f"date count exceeds limit")

    if plan is not None and panel.data_source_policy_id != plan.data_source_policy_id:
        raise PanelPolicyMismatchError(
            code="policy_mismatch",
            message=(
                f"panel policy {panel.data_source_policy_id!r} "
                f"does not match plan policy {plan.data_source_policy_id!r}"
            ),
        )

    if plan is not None and plan.requires_adjusted_pricing:
        if not panel.prices_adjusted:
            raise AdjustedPriceViolationError(
                code="unadjusted_prices",
                message="plan requires adjusted prices but panel is not marked adjusted",
            )
        if "close" in frame.columns and "adjusted_close" not in frame.columns:
            raise AdjustedPriceViolationError(
                code="mixed_price_series",
                message="panel appears to supply unadjusted close without adjusted_close",
            )
        prov_close = panel.field_provenance.get("close")
        prov_adj = panel.field_provenance.get("adjusted_close")
        if prov_close and prov_adj and prov_close.is_adjusted is False and prov_adj.is_adjusted is True:
            raise AdjustedPriceViolationError(
                code="mixed_adjusted_unadjusted",
                message="mixed adjusted and unadjusted price metadata",
            )

    registry = build_default_field_registry()
    for field_id, prov in panel.field_provenance.items():
        spec = registry.get(field_id)
        if spec and spec.is_outcome_label:
            raise InvalidInputPanelError(
                code="forbidden_outcome_field",
                message=f"outcome field in provenance: {field_id}",
                context=field_id,
            )
        if prov.pit_state == PitProvenanceState.FORBIDDEN:
            raise InvalidInputPanelError(
                code="forbidden_field_provenance",
                message=f"field provenance marked FORBIDDEN: {field_id}",
                context=field_id,
            )


from dataclasses import dataclass, field


@dataclass
class OperatorDiagnosticsCollector:
    invalid_log_domain_count: int = 0
    zero_denominator_count: int = 0
    insufficient_rolling_count: int = 0
    insufficient_cross_section_count: int = 0
    zero_variance_zscore_count: int = 0
    small_neutralization_group_count: int = 0
    regression_failure_count: int = 0
    warm_up_rows: int = 0

    def to_model(self) -> "OperatorDiagnostics":
        return OperatorDiagnostics(
            invalid_log_domain_count=self.invalid_log_domain_count,
            zero_denominator_count=self.zero_denominator_count,
            insufficient_rolling_count=self.insufficient_rolling_count,
            insufficient_cross_section_count=self.insufficient_cross_section_count,
            zero_variance_zscore_count=self.zero_variance_zscore_count,
            small_neutralization_group_count=self.small_neutralization_group_count,
            regression_failure_count=self.regression_failure_count,
            warm_up_rows=self.warm_up_rows,
        )


class OperatorDiagnostics(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    invalid_log_domain_count: int = 0
    zero_denominator_count: int = 0
    insufficient_rolling_count: int = 0
    insufficient_cross_section_count: int = 0
    zero_variance_zscore_count: int = 0
    small_neutralization_group_count: int = 0
    regression_failure_count: int = 0
    warm_up_rows: int = 0


@dataclass
class NeutralizationDiagnostics:
    key: str
    dates_processed: int = 0
    groups_processed: int = 0
    rows_neutralized: int = 0
    rows_missing_classification: int = 0
    rows_small_group: int = 0
    regression_failures: int = 0


class FactorExecutionResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    formula_hash_value: str
    plan_hash_value: str
    execution_hash_value: str
    executor_version: str
    panel_content_hash: str
    data_source_policy_id: str
    provider_id: str
    factor_values: Any
    valid_mask: Any
    eligibility_mask: Any
    start_date: date
    end_date: date
    symbol_count: int
    date_count: int
    row_count: int
    valid_output_count: int
    missing_output_count: int
    coverage_pct: float
    coverage_by_date: dict[str, float] = Field(default_factory=dict)
    coverage_by_symbol: dict[str, float] = Field(default_factory=dict)
    field_provenance: list[Any] = Field(default_factory=list)
    derived_field_provenance: list[Any] = Field(default_factory=list)
    operator_diagnostics: OperatorDiagnostics = Field(default_factory=OperatorDiagnostics)
    neutralization_diagnostics: list[NeutralizationDiagnostics] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    determinism_metadata: dict[str, str] = Field(default_factory=dict)
