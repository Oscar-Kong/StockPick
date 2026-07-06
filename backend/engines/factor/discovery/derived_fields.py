"""Trusted derived-field registry for Factor Discovery execution."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import pandas as pd

from engines.factor.discovery.execution_errors import DerivedFieldError, MissingFieldDataError
from engines.factor.discovery.provenance import (
    ExecutedFieldProvenance,
    PanelFieldSourceType,
    PitProvenanceState,
)

DERIVED_FIELD_REGISTRY_VERSION = "factor-derived-fields-v1"


@dataclass(frozen=True)
class DerivedFieldSpec:
    field_id: str
    derivation_version: str
    primitive_dependencies: tuple[str, ...]
    required_history_sessions: int
    requires_adjusted_price: bool
    compute: Callable[[dict[str, pd.Series], pd.Index], pd.Series]


def _per_symbol(series: pd.Series, fn: Callable[[pd.Series], pd.Series]) -> pd.Series:
    return series.groupby(level="symbol", group_keys=False).apply(fn)


def _compute_return_1d(primitives: dict[str, pd.Series], index: pd.Index) -> pd.Series:
    price = primitives["adjusted_close"].reindex(index)
    out = price.groupby(level="symbol", group_keys=False).pct_change(1)
    out.name = "return_1d"
    return out.reindex(index)


def _compute_return_126d(primitives: dict[str, pd.Series], index: pd.Index) -> pd.Series:
    price = primitives["adjusted_close"].reindex(index)
    out = price.groupby(level="symbol", group_keys=False).pct_change(126)
    out.name = "return_126d"
    return out.reindex(index)


def _compute_relative_volume(primitives: dict[str, pd.Series], index: pd.Index) -> pd.Series:
    vol = primitives["volume"].reindex(index)

    def _rel(s: pd.Series) -> pd.Series:
        mean20 = s.rolling(window=20, min_periods=20).mean()
        rel = s / mean20
        return rel.where(mean20 > 0)

    out = vol.groupby(level="symbol", group_keys=False).apply(_rel).reindex(index)
    out.name = "relative_volume"
    return out


_DERIVED: dict[str, DerivedFieldSpec] = {
    "return_1d": DerivedFieldSpec(
        field_id="return_1d",
        derivation_version="return_pct_v1",
        primitive_dependencies=("adjusted_close",),
        required_history_sessions=1,
        requires_adjusted_price=True,
        compute=_compute_return_1d,
    ),
    "return_126d": DerivedFieldSpec(
        field_id="return_126d",
        derivation_version="return_pct_v1",
        primitive_dependencies=("adjusted_close",),
        required_history_sessions=126,
        requires_adjusted_price=True,
        compute=_compute_return_126d,
    ),
    "relative_volume": DerivedFieldSpec(
        field_id="relative_volume",
        derivation_version="volume_ratio_ma20_v1",
        primitive_dependencies=("volume",),
        required_history_sessions=20,
        requires_adjusted_price=False,
        compute=_compute_relative_volume,
    ),
}


def get_derived_field_spec(field_id: str) -> DerivedFieldSpec | None:
    return _DERIVED.get(field_id)


def list_derived_field_ids() -> frozenset[str]:
    return frozenset(_DERIVED)


def materialize_derived_field(
    field_id: str,
    *,
    primitives: dict[str, pd.Series],
    index: pd.Index,
    provider_id: str,
) -> tuple[pd.Series, ExecutedFieldProvenance]:
    spec = _DERIVED.get(field_id)
    if spec is None:
        raise DerivedFieldError(
            code="unknown_derived_field",
            message=f"no derived field spec for {field_id}",
            context=field_id,
        )
    for dep in spec.primitive_dependencies:
        if dep not in primitives:
            raise MissingFieldDataError(
                code="missing_primitive",
                message=f"derived field {field_id} requires primitive {dep}",
                context=dep,
            )
    values = spec.compute(primitives, index)
    missing = int(values.isna().sum())
    prov = ExecutedFieldProvenance(
        field_id=field_id,
        source_type=PanelFieldSourceType.DERIVED,
        pit_state=PitProvenanceState.DERIVED_FROM_VERIFIED_PIT,
        provider_id=provider_id,
        derivation_version=spec.derivation_version,
        primitive_dependencies=list(spec.primitive_dependencies),
        is_adjusted=spec.requires_adjusted_price,
        missing_value_count=missing,
    )
    return values, prov


def register_derived_field_for_tests(spec: DerivedFieldSpec) -> None:
    if spec.field_id in _DERIVED:
        raise ValueError(f"duplicate derived field: {spec.field_id}")
    _DERIVED[spec.field_id] = spec
