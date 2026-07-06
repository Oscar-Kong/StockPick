"""Factor Discovery field registry and data-source policy contracts."""
from __future__ import annotations

from enum import Enum
from typing import Iterable

from pydantic import BaseModel, ConfigDict, Field

from models.schemas_factor_discovery import InputDataClass

REGISTRY_VERSION = "factor-field-registry-v1"


class FieldAvailability(str, Enum):
    AVAILABLE = "available"
    DERIVED_PANEL = "derived_panel"
    UNAVAILABLE = "unavailable"


class FieldTemporalScope(str, Enum):
    TIME_SERIES = "time_series"
    CROSS_SECTIONAL = "cross_sectional"
    BOTH = "both"


class FactorFieldSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    field_id: str
    display_label: str
    data_class: InputDataClass
    description: str
    unit: str | None = None
    factor_input_allowed: bool = True
    is_outcome_label: bool = False
    requires_point_in_time: bool = False
    requires_publication_lag: bool = False
    min_publication_lag_sessions: int = 0
    requires_adjusted_price: bool = False
    temporal_scope: FieldTemporalScope = FieldTemporalScope.TIME_SERIES
    availability: FieldAvailability = FieldAvailability.AVAILABLE
    compatible_policy_ids: frozenset[str] = frozenset()


class FactorDataSourcePolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    policy_id: str
    display_label: str
    description: str
    adjusted_prices_required: bool
    single_provider_per_run: bool = True
    provider_must_be_pinned: bool = True
    mixed_adjusted_unadjusted_forbidden: bool = True
    version: str = "1"


class FactorFieldRegistry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: str = REGISTRY_VERSION
    fields: dict[str, FactorFieldSpec]

    def get(self, field_id: str) -> FactorFieldSpec | None:
        return self.fields.get(field_id)

    def require(self, field_id: str) -> FactorFieldSpec:
        spec = self.get(field_id)
        if spec is None:
            raise KeyError(field_id)
        return spec


_RESEARCH_POLICY = FactorDataSourcePolicy(
    policy_id="research_adjusted_daily_v1",
    display_label="Research adjusted daily v1",
    description=(
        "Research-grade adjusted daily OHLCV with a single pinned provider per experiment; "
        "mixed adjusted/unadjusted price series forbidden."
    ),
    adjusted_prices_required=True,
)


def default_data_source_policy() -> FactorDataSourcePolicy:
    return _RESEARCH_POLICY


def _build_default_fields() -> dict[str, FactorFieldSpec]:
    policy = _RESEARCH_POLICY.policy_id
    compat = frozenset({policy})
    return {
        "adjusted_close": FactorFieldSpec(
            field_id="adjusted_close",
            display_label="Adjusted close",
            data_class=InputDataClass.PRICE,
            description="Split/dividend-adjusted daily close.",
            unit="USD",
            requires_adjusted_price=True,
            temporal_scope=FieldTemporalScope.TIME_SERIES,
            compatible_policy_ids=compat,
        ),
        "volume": FactorFieldSpec(
            field_id="volume",
            display_label="Volume",
            data_class=InputDataClass.VOLUME,
            description="Daily share volume.",
            temporal_scope=FieldTemporalScope.TIME_SERIES,
            compatible_policy_ids=compat,
        ),
        "sector": FactorFieldSpec(
            field_id="sector",
            display_label="Sector",
            data_class=InputDataClass.SECTOR,
            description="Sector classification code.",
            requires_point_in_time=True,
            temporal_scope=FieldTemporalScope.CROSS_SECTIONAL,
            compatible_policy_ids=compat,
        ),
        "industry": FactorFieldSpec(
            field_id="industry",
            display_label="Industry",
            data_class=InputDataClass.INDUSTRY,
            description="Industry classification code.",
            requires_point_in_time=True,
            temporal_scope=FieldTemporalScope.CROSS_SECTIONAL,
            compatible_policy_ids=compat,
        ),
        "close": FactorFieldSpec(
            field_id="close",
            display_label="Close",
            data_class=InputDataClass.PRICE,
            description="Unadjusted daily close; incompatible with research_adjusted_daily_v1.",
            unit="USD",
            requires_adjusted_price=False,
            temporal_scope=FieldTemporalScope.TIME_SERIES,
            compatible_policy_ids=frozenset(),
        ),
        "market_cap": FactorFieldSpec(
            field_id="market_cap",
            display_label="Market capitalization",
            data_class=InputDataClass.MARKET_CAP,
            description="Cross-sectional market cap snapshot.",
            unit="USD",
            requires_point_in_time=True,
            temporal_scope=FieldTemporalScope.CROSS_SECTIONAL,
            compatible_policy_ids=compat,
        ),
        "free_cash_flow": FactorFieldSpec(
            field_id="free_cash_flow",
            display_label="Free cash flow",
            data_class=InputDataClass.CASH_FLOW,
            description="Fundamental cash flow; publication lag applies in Phase 3.",
            requires_point_in_time=True,
            requires_publication_lag=True,
            min_publication_lag_sessions=45,
            temporal_scope=FieldTemporalScope.BOTH,
            compatible_policy_ids=compat,
        ),
        "return_126d": FactorFieldSpec(
            field_id="return_126d",
            display_label="126-session return",
            data_class=InputDataClass.RETURN,
            description="Precomputed 126-session return panel field for research fixtures.",
            availability=FieldAvailability.DERIVED_PANEL,
            requires_adjusted_price=True,
            temporal_scope=FieldTemporalScope.TIME_SERIES,
            compatible_policy_ids=compat,
        ),
        "return_1d": FactorFieldSpec(
            field_id="return_1d",
            display_label="1-session return",
            data_class=InputDataClass.RETURN,
            description="Precomputed 1-session return panel field.",
            availability=FieldAvailability.DERIVED_PANEL,
            requires_adjusted_price=True,
            temporal_scope=FieldTemporalScope.TIME_SERIES,
            compatible_policy_ids=compat,
        ),
        "relative_volume": FactorFieldSpec(
            field_id="relative_volume",
            display_label="Relative volume",
            data_class=InputDataClass.LIQUIDITY,
            description="Volume relative to trailing average.",
            availability=FieldAvailability.DERIVED_PANEL,
            temporal_scope=FieldTemporalScope.TIME_SERIES,
            compatible_policy_ids=compat,
        ),
        "operating_cash_flow_growth": FactorFieldSpec(
            field_id="operating_cash_flow_growth",
            display_label="Operating cash flow growth",
            data_class=InputDataClass.GROWTH,
            description="Conceptual growth field; not yet available in research loaders.",
            availability=FieldAvailability.UNAVAILABLE,
            requires_point_in_time=True,
            requires_publication_lag=True,
            min_publication_lag_sessions=45,
            compatible_policy_ids=compat,
        ),
        "gross_margin_volatility": FactorFieldSpec(
            field_id="gross_margin_volatility",
            display_label="Gross margin volatility",
            data_class=InputDataClass.VOLATILITY,
            description="Conceptual profitability volatility field; not yet available.",
            availability=FieldAvailability.UNAVAILABLE,
            requires_point_in_time=True,
            compatible_policy_ids=compat,
        ),
        "forward_return_5d": FactorFieldSpec(
            field_id="forward_return_5d",
            display_label="Forward 5d return",
            data_class=InputDataClass.RETURN,
            description="Outcome label; forbidden as factor input.",
            is_outcome_label=True,
            factor_input_allowed=False,
            temporal_scope=FieldTemporalScope.TIME_SERIES,
        ),
        "forward_return_21d": FactorFieldSpec(
            field_id="forward_return_21d",
            display_label="Forward 21d return",
            data_class=InputDataClass.RETURN,
            description="Outcome label; forbidden as factor input.",
            is_outcome_label=True,
            factor_input_allowed=False,
        ),
        "future_return": FactorFieldSpec(
            field_id="future_return",
            display_label="Future return",
            data_class=InputDataClass.RETURN,
            description="Generic outcome label; forbidden as factor input.",
            is_outcome_label=True,
            factor_input_allowed=False,
        ),
        "target_return": FactorFieldSpec(
            field_id="target_return",
            display_label="Target return",
            data_class=InputDataClass.RETURN,
            description="Generic outcome label; forbidden as factor input.",
            is_outcome_label=True,
            factor_input_allowed=False,
        ),
    }


def build_default_field_registry(*, extra_fields: Iterable[FactorFieldSpec] | None = None) -> FactorFieldRegistry:
    fields = _build_default_fields()
    if extra_fields:
        for spec in extra_fields:
            if spec.field_id in fields:
                raise ValueError(f"duplicate field registration: {spec.field_id}")
            fields[spec.field_id] = spec
    return FactorFieldRegistry(fields=fields)
