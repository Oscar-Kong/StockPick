"""Resolve compiled plan fields against a supplied input panel."""
from __future__ import annotations

import pandas as pd

from engines.factor.discovery.compiler import CompiledFactorPlan
from engines.factor.discovery.derived_fields import get_derived_field_spec, list_derived_field_ids, materialize_derived_field
from engines.factor.discovery.execution_errors import (
    AdjustedPriceViolationError,
    MissingFieldDataError,
    PointInTimeViolationError,
)
from engines.factor.discovery.field_registry import FieldAvailability, build_default_field_registry
from engines.factor.discovery.panel_models import FactorExecutionConfig, FactorInputPanel
from engines.factor.discovery.provenance import ExecutedFieldProvenance, PanelFieldSourceType, PitProvenanceState


class ResolvedFieldBundle:
    def __init__(self) -> None:
        self.series: dict[str, pd.Series] = {}
        self.provenance: dict[str, ExecutedFieldProvenance] = {}


def _pit_ok(prov_state: PitProvenanceState, *, strict: bool, requires_pit: bool) -> bool:
    if not requires_pit:
        return True
    if prov_state in {PitProvenanceState.VERIFIED_PIT, PitProvenanceState.DERIVED_FROM_VERIFIED_PIT}:
        return True
    if prov_state == PitProvenanceState.STATIC_NON_PIT and not strict:
        return True
    return False


def resolve_fields(
    plan: CompiledFactorPlan,
    panel: FactorInputPanel,
    *,
    config: FactorExecutionConfig,
) -> ResolvedFieldBundle:
    registry = build_default_field_registry()
    bundle = ResolvedFieldBundle()
    index = panel.frame.index
    primitives: dict[str, pd.Series] = {}

    for field_id, prov in panel.field_provenance.items():
        if field_id in panel.frame.columns and prov.source_type == PanelFieldSourceType.SUPPLIED_PRIMITIVE:
            primitives[field_id] = panel.frame[field_id].astype(float)

    for field_id in plan.required_field_ids:
        spec = registry.require(field_id)
        if spec.availability == FieldAvailability.UNAVAILABLE:
            raise MissingFieldDataError(
                code="unavailable_field",
                message=f"field is not available for execution: {field_id}",
                context=field_id,
            )
        if spec.is_outcome_label or not spec.factor_input_allowed:
            raise MissingFieldDataError(
                code="forbidden_field",
                message=f"field cannot be executed: {field_id}",
                context=field_id,
            )

        panel_prov = panel.field_provenance.get(field_id)
        derived_spec = get_derived_field_spec(field_id)

        if field_id in panel.frame.columns and panel_prov is not None:
            if spec.requires_adjusted_price and panel_prov.is_adjusted is False:
                raise AdjustedPriceViolationError(
                    code="not_adjusted",
                    message=f"field {field_id} requires adjusted prices",
                    context=field_id,
                )
            if not _pit_ok(
                panel_prov.pit_state,
                strict=config.strict_pit_mode,
                requires_pit=spec.requires_point_in_time,
            ):
                raise PointInTimeViolationError(
                    code="pit_unverified",
                    message=f"field {field_id} lacks verified PIT provenance",
                    context=field_id,
                )
            series = panel.frame[field_id].astype(float)
            missing = int(series.isna().sum())
            bundle.series[field_id] = series
            bundle.provenance[field_id] = ExecutedFieldProvenance(
                field_id=field_id,
                source_type=panel_prov.source_type,
                pit_state=panel_prov.pit_state,
                provider_id=panel.provider_id,
                derivation_version=panel_prov.derivation_version,
                primitive_dependencies=list(panel_prov.primitive_dependencies),
                is_adjusted=panel_prov.is_adjusted,
                publication_lag_sessions_applied=panel_prov.publication_lag_sessions_applied,
                earliest_valid_date=panel_prov.earliest_valid_date,
                missing_value_count=missing,
                warnings=list(panel_prov.warnings),
            )
            if panel_prov.source_type == PanelFieldSourceType.SUPPLIED_PRIMITIVE:
                primitives[field_id] = series
            continue

        if derived_spec is not None or field_id in list_derived_field_ids():
            values, prov = materialize_derived_field(
                field_id,
                primitives=primitives,
                index=index,
                provider_id=panel.provider_id,
            )
            bundle.series[field_id] = values
            bundle.provenance[field_id] = prov
            continue

        raise MissingFieldDataError(
            code="missing_field_data",
            message=f"required field not present in panel and not derivable: {field_id}",
            context=field_id,
        )

    return bundle
