"""Factor Discovery contracts — declarative models only (no evaluation or LLM)."""
from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import date
from enum import Enum
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SCHEMA_VERSION = "factor-discovery-v1"
MAX_AST_DEPTH = 32
FIELD_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
SEMVER_PATTERN = re.compile(r"^\d+\.\d+\.\d+(-[a-zA-Z0-9.]+)?$")

# --- Enums ---


class FactorLifecycleStatus(str, Enum):
    DRAFT = "DRAFT"
    COMPILED = "COMPILED"
    RESEARCHING = "RESEARCHING"
    REJECTED = "REJECTED"
    PROMISING = "PROMISING"
    VALIDATED = "VALIDATED"
    PAPER = "PAPER"
    PRODUCTION = "PRODUCTION"
    RETIRED = "RETIRED"


class FactorDirection(str, Enum):
    HIGHER_IS_BETTER = "HIGHER_IS_BETTER"
    LOWER_IS_BETTER = "LOWER_IS_BETTER"


class InputDataClass(str, Enum):
    PRICE = "PRICE"
    RETURN = "RETURN"
    VOLUME = "VOLUME"
    VOLATILITY = "VOLATILITY"
    LIQUIDITY = "LIQUIDITY"
    MARKET_CAP = "MARKET_CAP"
    FUNDAMENTAL = "FUNDAMENTAL"
    VALUATION = "VALUATION"
    PROFITABILITY = "PROFITABILITY"
    GROWTH = "GROWTH"
    BALANCE_SHEET = "BALANCE_SHEET"
    CASH_FLOW = "CASH_FLOW"
    ANALYST = "ANALYST"
    SECTOR = "SECTOR"
    INDUSTRY = "INDUSTRY"
    MACRO = "MACRO"


class ResearchPeriodRole(str, Enum):
    DISCOVERY = "DISCOVERY"
    VALIDATION = "VALIDATION"
    SEALED_TEST = "SEALED_TEST"


class UnaryOperator(str, Enum):
    ABS = "ABS"
    NEGATE = "NEGATE"
    LOG = "LOG"
    SIGN = "SIGN"


class BinaryOperator(str, Enum):
    ADD = "ADD"
    SUBTRACT = "SUBTRACT"
    MULTIPLY = "MULTIPLY"
    DIVIDE = "DIVIDE"
    MIN = "MIN"
    MAX = "MAX"


class RollingOperator(str, Enum):
    LAG = "LAG"
    DELTA = "DELTA"
    PCT_CHANGE = "PCT_CHANGE"
    ROLLING_MEAN = "ROLLING_MEAN"
    ROLLING_STD = "ROLLING_STD"
    ROLLING_MIN = "ROLLING_MIN"
    ROLLING_MAX = "ROLLING_MAX"
    ROLLING_SUM = "ROLLING_SUM"
    ROLLING_CORRELATION = "ROLLING_CORRELATION"


class CrossSectionOperator(str, Enum):
    RANK = "RANK"
    PERCENTILE_RANK = "PERCENTILE_RANK"
    ZSCORE = "ZSCORE"
    WINSORIZE = "WINSORIZE"


class NeutralizationKey(str, Enum):
    SECTOR = "SECTOR"
    INDUSTRY = "INDUSTRY"
    MARKET_CAP = "MARKET_CAP"


class ZeroDivisionPolicy(str, Enum):
    NULL = "null"
    ZERO = "zero"
    EPSILON = "epsilon"


class LogDomainPolicy(str, Enum):
    NULL_ON_NON_POSITIVE = "null_on_non_positive"
    ABS_LOG = "abs_log"


class HypothesisSource(str, Enum):
    USER = "user"
    LLM = "llm"
    BRIEF = "brief"
    REVISION = "revision"


# --- Lifecycle transitions ---

_ALLOWED_TRANSITIONS: dict[FactorLifecycleStatus, frozenset[FactorLifecycleStatus]] = {
    FactorLifecycleStatus.DRAFT: frozenset({FactorLifecycleStatus.COMPILED, FactorLifecycleStatus.REJECTED}),
    FactorLifecycleStatus.COMPILED: frozenset(
        {FactorLifecycleStatus.RESEARCHING, FactorLifecycleStatus.REJECTED}
    ),
    FactorLifecycleStatus.RESEARCHING: frozenset(
        {FactorLifecycleStatus.PROMISING, FactorLifecycleStatus.REJECTED}
    ),
    FactorLifecycleStatus.PROMISING: frozenset(
        {
            FactorLifecycleStatus.RESEARCHING,
            FactorLifecycleStatus.VALIDATED,
            FactorLifecycleStatus.REJECTED,
        }
    ),
    FactorLifecycleStatus.VALIDATED: frozenset(
        {FactorLifecycleStatus.PAPER, FactorLifecycleStatus.RETIRED}
    ),
    FactorLifecycleStatus.PAPER: frozenset(
        {
            FactorLifecycleStatus.PRODUCTION,
            FactorLifecycleStatus.RETIRED,
            FactorLifecycleStatus.RESEARCHING,
        }
    ),
    FactorLifecycleStatus.PRODUCTION: frozenset({FactorLifecycleStatus.RETIRED}),
    FactorLifecycleStatus.REJECTED: frozenset({FactorLifecycleStatus.DRAFT}),
    FactorLifecycleStatus.RETIRED: frozenset({FactorLifecycleStatus.DRAFT}),
}


def can_transition_factor_status(current: FactorLifecycleStatus, target: FactorLifecycleStatus) -> bool:
    if current == target:
        return True
    return target in _ALLOWED_TRANSITIONS.get(current, frozenset())


def validate_factor_status_transition(current: FactorLifecycleStatus, target: FactorLifecycleStatus) -> None:
    if not can_transition_factor_status(current, target):
        raise ValueError(f"illegal lifecycle transition: {current.value} -> {target.value}")


# --- AST nodes ---


class _AstBase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class FieldNode(_AstBase):
    kind: Literal["FIELD"] = "FIELD"
    field_id: str

    @field_validator("field_id")
    @classmethod
    def _valid_field(cls, v: str) -> str:
        if not FIELD_ID_PATTERN.match(v):
            raise ValueError(f"invalid field_id: {v}")
        return v


class ConstantNode(_AstBase):
    kind: Literal["CONSTANT"] = "CONSTANT"
    value: float

    @field_validator("value")
    @classmethod
    def _finite(cls, v: float) -> float:
        if not math.isfinite(v):
            raise ValueError("constant must be finite")
        return v


class UnaryNode(_AstBase):
    kind: Literal["UNARY"] = "UNARY"
    op: UnaryOperator
    child: "AstNode"
    log_policy: LogDomainPolicy = LogDomainPolicy.NULL_ON_NON_POSITIVE


class BinaryNode(_AstBase):
    kind: Literal["BINARY"] = "BINARY"
    op: BinaryOperator
    left: "AstNode"
    right: "AstNode"
    zero_policy: ZeroDivisionPolicy = ZeroDivisionPolicy.NULL


class RollingNode(_AstBase):
    kind: Literal["ROLLING"] = "ROLLING"
    op: RollingOperator
    child: "AstNode"
    right: "AstNode | None" = None
    window: int = Field(ge=1, le=2520)
    min_periods: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def _rolling_arity(self) -> RollingNode:
        if self.op == RollingOperator.ROLLING_CORRELATION:
            if self.right is None:
                raise ValueError("ROLLING_CORRELATION requires right child")
        elif self.right is not None:
            raise ValueError(f"{self.op.value} must not have right child")
        if self.min_periods is not None and self.min_periods > self.window:
            raise ValueError("min_periods cannot exceed window")
        return self


class CrossSectionNode(_AstBase):
    kind: Literal["CROSS_SECTIONAL"] = "CROSS_SECTIONAL"
    op: CrossSectionOperator
    child: "AstNode"
    winsorize_lower: float = Field(default=0.01, ge=0.0, lt=1.0)
    winsorize_upper: float = Field(default=0.99, gt=0.0, le=1.0)

    @model_validator(mode="after")
    def _winsorize_bounds(self) -> CrossSectionNode:
        if self.op == CrossSectionOperator.WINSORIZE and self.winsorize_lower >= self.winsorize_upper:
            raise ValueError("winsorize_lower must be < winsorize_upper")
        return self


class NeutralizeNode(_AstBase):
    kind: Literal["NEUTRALIZE"] = "NEUTRALIZE"
    key: NeutralizationKey
    child: "AstNode"


class ConditionalNode(_AstBase):
    kind: Literal["CONDITIONAL"] = "CONDITIONAL"
    condition: "AstNode"
    if_true: "AstNode"
    if_false: "AstNode"


AstNode = Annotated[
    Union[
        FieldNode,
        ConstantNode,
        UnaryNode,
        BinaryNode,
        RollingNode,
        CrossSectionNode,
        NeutralizeNode,
        ConditionalNode,
    ],
    Field(discriminator="kind"),
]

UnaryNode.model_rebuild()
BinaryNode.model_rebuild()
RollingNode.model_rebuild()
CrossSectionNode.model_rebuild()
NeutralizeNode.model_rebuild()
ConditionalNode.model_rebuild()


def ast_depth(node: AstNode, *, _depth: int = 0) -> int:
    if _depth > MAX_AST_DEPTH:
        raise ValueError(f"AST exceeds maximum depth of {MAX_AST_DEPTH}")
    if isinstance(node, FieldNode | ConstantNode):
        return _depth + 1
    if isinstance(node, UnaryNode | CrossSectionNode | NeutralizeNode):
        return ast_depth(node.child, _depth=_depth + 1)
    if isinstance(node, RollingNode):
        if node.right is not None:
            return max(
                ast_depth(node.child, _depth=_depth + 1),
                ast_depth(node.right, _depth=_depth + 1),
            )
        return ast_depth(node.child, _depth=_depth + 1)
    if isinstance(node, BinaryNode):
        return max(ast_depth(node.left, _depth=_depth + 1), ast_depth(node.right, _depth=_depth + 1))
    if isinstance(node, ConditionalNode):
        return max(
            ast_depth(node.condition, _depth=_depth + 1),
            ast_depth(node.if_true, _depth=_depth + 1),
            ast_depth(node.if_false, _depth=_depth + 1),
        )
    raise TypeError(f"unknown AST node: {type(node)}")


def collect_field_ids(node: AstNode) -> frozenset[str]:
    if isinstance(node, FieldNode):
        return frozenset({node.field_id})
    if isinstance(node, ConstantNode):
        return frozenset()
    if isinstance(node, UnaryNode | CrossSectionNode | NeutralizeNode):
        return collect_field_ids(node.child)
    if isinstance(node, RollingNode):
        ids = collect_field_ids(node.child)
        if node.right is not None:
            ids = ids | collect_field_ids(node.right)
        return ids
    if isinstance(node, BinaryNode):
        return collect_field_ids(node.left) | collect_field_ids(node.right)
    if isinstance(node, ConditionalNode):
        return (
            collect_field_ids(node.condition)
            | collect_field_ids(node.if_true)
            | collect_field_ids(node.if_false)
        )
    return frozenset()


def _scrub_canonical_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("kind") == "CROSS_SECTIONAL" and payload.get("op") != "WINSORIZE":
        payload.pop("winsorize_lower", None)
        payload.pop("winsorize_upper", None)
    for key in ("child", "left", "right", "condition", "if_true", "if_false"):
        child = payload.get(key)
        if isinstance(child, dict):
            payload[key] = _scrub_canonical_payload(child)
    return payload


def canonical_ast_payload(node: AstNode) -> dict[str, Any]:
    """JSON-serializable canonical AST dict for hashing."""
    ast_depth(node)
    payload = node.model_dump(mode="json", exclude_none=True)
    return _scrub_canonical_payload(payload)


def formula_hash(expression: AstNode) -> str:
    """Deterministic SHA-256 over canonical formula semantics."""
    payload = canonical_ast_payload(expression)
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


# --- Hypothesis & definition ---


class FactorHypothesis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hypothesis_id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=256)
    economic_rationale: str = Field(min_length=1)
    expected_mechanism: str = Field(min_length=1)
    expected_direction: FactorDirection
    intended_universe: str = Field(min_length=1, max_length=64)
    holding_period_sessions: int = Field(ge=1, le=504)
    rebalance_frequency: str = Field(min_length=1, max_length=32)
    required_data_classes: list[InputDataClass] = Field(min_length=1)
    known_risks: list[str] = Field(default_factory=list)
    expected_failure_conditions: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    creation_source: HypothesisSource = HypothesisSource.USER
    schema_version: str = SCHEMA_VERSION

    @field_validator("required_data_classes")
    @classmethod
    def _dedupe_data_classes(cls, v: list[InputDataClass]) -> list[InputDataClass]:
        seen: list[InputDataClass] = []
        for item in v:
            if item not in seen:
                seen.append(item)
        return seen

    @field_validator("tags")
    @classmethod
    def _normalize_tags(cls, v: list[str]) -> list[str]:
        return sorted({t.strip().lower() for t in v if t.strip()})


class FactorDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    factor_id: str = Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_]*$")
    version: str = Field(min_length=1, max_length=32)
    display_name: str = Field(min_length=1, max_length=128)
    hypothesis_id: str | None = None
    hypothesis: FactorHypothesis | None = None
    expression: AstNode
    expected_direction: FactorDirection
    intended_universe: str = Field(min_length=1, max_length=64)
    rebalance_frequency: str = Field(min_length=1, max_length=32)
    holding_period_sessions: int = Field(ge=1, le=504)
    required_fields: list[str] = Field(default_factory=list)
    data_source_policy_id: str = Field(default="research_adjusted_daily_v1", max_length=64)
    missing_value_policy: str = Field(default="exclude_symbol", max_length=64)
    outlier_policy: str = Field(default="winsorize_cs", max_length=64)
    neutralization_keys: list[NeutralizationKey] = Field(default_factory=list)
    lifecycle_status: FactorLifecycleStatus = FactorLifecycleStatus.DRAFT
    parent_factor_id: str | None = None
    parent_version: str | None = None
    schema_version: str = SCHEMA_VERSION
    notes: str = ""

    @field_validator("version", "parent_version")
    @classmethod
    def _semver(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if not SEMVER_PATTERN.match(v):
            raise ValueError(f"version must be semver-style: {v}")
        return v

    @model_validator(mode="after")
    def _validate_lineage_and_fields(self) -> FactorDefinition:
        ast_depth(self.expression)
        if self.parent_factor_id == self.factor_id:
            raise ValueError("factor cannot be its own parent")
        derived = sorted(collect_field_ids(self.expression))
        if self.required_fields:
            missing = set(derived) - set(self.required_fields)
            if missing:
                raise ValueError(f"required_fields missing AST fields: {sorted(missing)}")
        else:
            object.__setattr__(self, "required_fields", derived)
        return self

    def formula_hash(self) -> str:
        return formula_hash(self.expression)

    def definition_identity_hash(self) -> str:
        """Hash including factor_id + version + formula (excludes lifecycle and notes)."""
        payload = {
            "factor_id": self.factor_id,
            "version": self.version,
            "expression": canonical_ast_payload(self.expression),
            "expected_direction": self.expected_direction.value,
            "data_source_policy_id": self.data_source_policy_id,
            "missing_value_policy": self.missing_value_policy,
            "outlier_policy": self.outlier_policy,
            "neutralization_keys": sorted(k.value for k in self.neutralization_keys),
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return f"sha256:{hashlib.sha256(canonical.encode('utf-8')).hexdigest()}"


# --- Period split ---


class DiscoveryPeriodSplit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    discovery_start: date
    discovery_end: date
    validation_start: date
    validation_end: date
    sealed_test_start: date
    sealed_test_end: date
    embargo_days: int = Field(default=0, ge=0, le=63)
    min_sealed_test_days: int = Field(default=63, ge=1, le=504)
    calendar: str = Field(default="XNYS", max_length=16)

    @model_validator(mode="after")
    def _chronology(self) -> DiscoveryPeriodSplit:
        if self.discovery_start > self.discovery_end:
            raise ValueError("discovery_start must be <= discovery_end")
        if self.validation_start > self.validation_end:
            raise ValueError("validation_start must be <= validation_end")
        if self.sealed_test_start > self.sealed_test_end:
            raise ValueError("sealed_test_start must be <= sealed_test_end")
        if self.discovery_end >= self.validation_start:
            raise ValueError("discovery_end must be before validation_start")
        if self.validation_end >= self.sealed_test_start:
            raise ValueError("validation_end must be before sealed_test_start")
        if self.embargo_days > 0:
            gap_d = (self.validation_start - self.discovery_end).days
            gap_v = (self.sealed_test_start - self.validation_end).days
            if gap_d < self.embargo_days or gap_v < self.embargo_days:
                raise ValueError("embargo_days requires larger gaps between periods")
        sealed_len = (self.sealed_test_end - self.sealed_test_start).days
        if sealed_len < self.min_sealed_test_days:
            raise ValueError(
                f"sealed test span ({sealed_len} calendar days) below min_sealed_test_days ({self.min_sealed_test_days})"
            )
        return self

    def role_for_date(self, value: date) -> ResearchPeriodRole | None:
        if self.discovery_start <= value <= self.discovery_end:
            return ResearchPeriodRole.DISCOVERY
        if self.validation_start <= value <= self.validation_end:
            return ResearchPeriodRole.VALIDATION
        if self.sealed_test_start <= value <= self.sealed_test_end:
            return ResearchPeriodRole.SEALED_TEST
        return None

    def to_json_dict(self) -> dict[str, str]:
        return {
            "discovery_start": self.discovery_start.isoformat(),
            "discovery_end": self.discovery_end.isoformat(),
            "validation_start": self.validation_start.isoformat(),
            "validation_end": self.validation_end.isoformat(),
            "sealed_test_start": self.sealed_test_start.isoformat(),
            "sealed_test_end": self.sealed_test_end.isoformat(),
            "embargo_days": str(self.embargo_days),
            "min_sealed_test_days": str(self.min_sealed_test_days),
            "calendar": self.calendar,
        }
