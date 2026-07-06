"""Runtime research period resolution from panel sessions."""
from __future__ import annotations

import hashlib
import json
from typing import Any

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from engines.factor.discovery.sessions import CanonicalSessionCalendar
from engines.factor.discovery.validation_errors import PeriodResolutionError
from engines.factor.discovery.validation_models import FactorValidationConfig
from models.schemas_factor_discovery import DiscoveryPeriodSplit, ResearchPeriodRole


class ResolvedResearchPeriods(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    discovery_sessions: tuple[str, ...]
    validation_sessions: tuple[str, ...]
    sealed_test_sessions: tuple[str, ...]
    embargo_excluded_sessions: tuple[str, ...]
    discovery_count: int
    validation_count: int
    sealed_test_count: int
    period_resolution_hash: str
    warnings: list[str] = Field(default_factory=list)


def _session_str(ts: pd.Timestamp) -> str:
    return pd.Timestamp(ts).strftime("%Y-%m-%d")


def resolve_research_periods(
    period_split: DiscoveryPeriodSplit,
    calendar: CanonicalSessionCalendar,
    *,
    config: FactorValidationConfig,
    canonical_session_hash_value: str | None = None,
) -> ResolvedResearchPeriods:
    warnings: list[str] = []
    discovery: list[str] = []
    validation: list[str] = []
    sealed: list[str] = []
    embargo_excluded: list[str] = []

    for sess in calendar.sessions:
        d = sess.date()
        role = period_split.role_for_date(d)
        s = _session_str(sess)
        if role == ResearchPeriodRole.DISCOVERY:
            discovery.append(s)
        elif role == ResearchPeriodRole.VALIDATION:
            validation.append(s)
        elif role == ResearchPeriodRole.SEALED_TEST:
            sealed.append(s)
        else:
            embargo_excluded.append(s)

    if len(discovery) < config.min_discovery_sessions:
        warnings.append(
            f"discovery sessions ({len(discovery)}) below min ({config.min_discovery_sessions})"
        )
    if len(validation) < config.min_validation_sessions:
        warnings.append(
            f"validation sessions ({len(validation)}) below min ({config.min_validation_sessions})"
        )
    if len(sealed) < config.min_sealed_test_sessions:
        warnings.append(
            f"sealed-test sessions ({len(sealed)}) below min ({config.min_sealed_test_sessions})"
        )

    overlap = set(discovery) & set(validation) & set(sealed)
    if overlap:
        raise PeriodResolutionError(
            code="period_overlap",
            message=f"sessions assigned to multiple roles: {sorted(overlap)[:5]}",
        )

    payload: dict[str, Any] = {
        "discovery": discovery,
        "validation": validation,
        "sealed": sealed,
        "embargo_excluded": embargo_excluded,
        "split": period_split.to_json_dict(),
    }
    if canonical_session_hash_value:
        payload["canonical_session_hash"] = canonical_session_hash_value
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    phash = f"sha256:{hashlib.sha256(canonical.encode()).hexdigest()}"

    return ResolvedResearchPeriods(
        discovery_sessions=tuple(discovery),
        validation_sessions=tuple(validation),
        sealed_test_sessions=tuple(sealed),
        embargo_excluded_sessions=tuple(embargo_excluded),
        discovery_count=len(discovery),
        validation_count=len(validation),
        sealed_test_count=len(sealed),
        period_resolution_hash=phash,
        warnings=warnings,
    )


def mask_for_sessions(index: pd.MultiIndex, sessions: tuple[str, ...]) -> pd.Series:
    sess_set = set(sessions)
    dates = index.get_level_values(0)
    mask = pd.Series(
        [pd.Timestamp(d).strftime("%Y-%m-%d") in sess_set for d in dates],
        index=index,
    )
    return mask
