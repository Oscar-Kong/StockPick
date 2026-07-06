"""Validation configuration and artifact contracts."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

VALIDATION_ENGINE_VERSION = "factor-validation-v1"
VALIDATION_ARTIFACT_SCHEMA_VERSION = "factor-validation-artifact-v1"


class FactorValidationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    outcome_horizons_sessions: tuple[int, ...] = (5, 21, 63)
    primary_horizon_sessions: int = 21
    min_cross_sectional_observations: int = 5
    quantile_count: int = 5
    rebalance_every_sessions: int = 21
    top_quantile_fraction: float = 0.2
    max_position_weight: float = 0.25
    execution_timing: Literal["next_session"] = "next_session"
    cost_model_id: str = "fixed_bps_v1"
    one_way_cost_bps: float = 10.0
    turnover_convention: Literal["one_way"] = "one_way"
    significance_level: float = 0.05
    multiple_testing_method: Literal["bonferroni", "benjamini_hochberg", "none"] = "benjamini_hochberg"
    declared_hypothesis_family_size: int | None = None
    min_mean_rank_ic: float = 0.02
    min_rank_ic_ir: float = 0.3
    min_positive_ic_pct: float = 0.52
    max_turnover_per_rebalance: float = 0.8
    max_drawdown: float = 0.5
    min_valid_date_coverage_pct: float = 0.5
    min_discovery_sessions: int = 20
    min_validation_sessions: int = 20
    min_sealed_test_sessions: int = 10
    walk_forward_mode: Literal["expanding", "rolling"] = "expanding"
    walk_forward_step_sessions: int = 21
    walk_forward_validation_sessions: int = 21
    min_walk_forward_folds: int = 2
    config_version: str = "factor-validation-config-v1"
    primary_significance_method: Literal["newey_west", "non_overlapping"] = "newey_west"
    newey_west_lag_policy: str = "floor_4x_horizon_over_3"
    significance_method_version: str = "factor-significance-v1"

    def canonical_payload(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class SealedTestAccess(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    authorization_type: str = "manual_research"
    reason: str
    requested_by: str
    approval_reference: str
    factor_id: str | None = None
    factor_version: str | None = None
    expected_formula_hash: str
    expected_plan_hash: str
    access_policy_version: str = "sealed-access-v1"

    def canonical_payload(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class GateRuleResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    rule_id: str
    category: str
    status: Literal["PASS", "FAIL", "INCONCLUSIVE", "NOT_EVALUATED"]
    actual: float | str | None = None
    threshold: float | str | None = None
    message: str = ""


class AcceptanceGateResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    overall_status: Literal["PASS", "FAIL", "INCONCLUSIVE", "NOT_EVALUATED"]
    rules: list[GateRuleResult] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class SealedTestStatus(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["SEALED", "OPENED", "INSUFFICIENT_DATA"]
    session_count: int
    start_date: str | None = None
    end_date: str | None = None
    opened: bool = False
    receipt_hash: str | None = None


class FactorValidationArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = VALIDATION_ARTIFACT_SCHEMA_VERSION
    validation_engine_version: str = VALIDATION_ENGINE_VERSION
    factor_id: str | None = None
    factor_version: str | None = None
    formula_hash: str
    plan_hash: str
    panel_hash: str
    canonical_session_hash: str = ""
    execution_hash: str
    validation_config_hash: str
    period_resolution_hash: str
    validation_artifact_hash: str
    factor_direction: str
    primary_horizon_sessions: int
    discovery_metrics: dict[str, Any] = Field(default_factory=dict)
    validation_metrics: dict[str, Any] = Field(default_factory=dict)
    sealed_test: SealedTestStatus
    sealed_test_metrics: dict[str, Any] | None = None
    walk_forward: dict[str, Any] = Field(default_factory=dict)
    robustness: dict[str, Any] = Field(default_factory=dict)
    quantile_results: dict[str, Any] = Field(default_factory=dict)
    portfolio_results: dict[str, Any] = Field(default_factory=dict)
    statistical_results: dict[str, Any] = Field(default_factory=dict)
    multiple_testing: dict[str, Any] = Field(default_factory=dict)
    redundancy: dict[str, Any] = Field(default_factory=dict)
    acceptance_gate: AcceptanceGateResult
    outcome_panel_hashes: dict[str, str] = Field(default_factory=dict)
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    determinism_metadata: dict[str, str] = Field(default_factory=dict)
