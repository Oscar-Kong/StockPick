"""Structured provenance for Factor Discovery execution."""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class PitProvenanceState(str, Enum):
    VERIFIED_PIT = "VERIFIED_PIT"
    DERIVED_FROM_VERIFIED_PIT = "DERIVED_FROM_VERIFIED_PIT"
    STATIC_NON_PIT = "STATIC_NON_PIT"
    UNVERIFIED = "UNVERIFIED"
    FORBIDDEN = "FORBIDDEN"


class PanelFieldSourceType(str, Enum):
    SUPPLIED_PRIMITIVE = "supplied_primitive"
    DERIVED = "derived"
    PIT_ALIGNED_FUNDAMENTAL = "pit_aligned_fundamental"
    CLASSIFICATION = "classification"
    EXPOSURE = "exposure"


class PanelFieldProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    field_id: str
    source_type: PanelFieldSourceType
    pit_state: PitProvenanceState
    provider_id: str
    source_policy_id: str
    derivation_version: str | None = None
    primitive_dependencies: list[str] = Field(default_factory=list)
    is_adjusted: bool | None = None
    publication_lag_sessions_applied: int = 0
    earliest_valid_date: str | None = None
    missing_value_count: int = 0
    warnings: list[str] = Field(default_factory=list)


class ExecutedFieldProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    field_id: str
    source_type: PanelFieldSourceType
    pit_state: PitProvenanceState
    provider_id: str
    derivation_version: str | None = None
    primitive_dependencies: list[str] = Field(default_factory=list)
    is_adjusted: bool | None = None
    publication_lag_sessions_applied: int = 0
    formula_lag_sessions: int = 0
    earliest_valid_date: str | None = None
    missing_value_count: int = 0
    warnings: list[str] = Field(default_factory=list)
