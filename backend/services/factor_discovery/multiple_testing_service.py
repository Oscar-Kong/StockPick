"""Multiple-testing family size derivation from attempt ledger."""
from __future__ import annotations

from dataclasses import dataclass

from engines.factor_discovery_models import FactorDiscoveryAttempt

ATTEMPT_COUNT_POLICY_VERSION = "distinct_formula_evaluations_v1"

EVALUATED_OUTCOMES = frozenset(
    {
        "validation_completed",
        "sealed_open_completed",
    }
)


@dataclass(frozen=True)
class FamilySizeResult:
    policy_version: str
    derived_family_size: int
    evaluated_formula_hashes: tuple[str, ...]
    declared_family_size: int | None
    effective_family_size: int
    stale_correction: bool = False


def derive_family_size(
    attempts: list[FactorDiscoveryAttempt],
    *,
    primary_horizon_sessions: int,
    validation_config_family_id: str,
    declared_family_size: int | None = None,
    policy_version: str = ATTEMPT_COUNT_POLICY_VERSION,
) -> FamilySizeResult:
    """Count distinct formula hashes that reached metric evaluation in this family."""
    if policy_version != ATTEMPT_COUNT_POLICY_VERSION:
        raise ValueError(f"unsupported attempt count policy: {policy_version}")

    seen: set[str] = set()
    for att in attempts:
        if att.outcome not in EVALUATED_OUTCOMES and not att.metric_evaluation_started:
            continue
        if att.primary_horizon_sessions != primary_horizon_sessions:
            continue
        if not att.formula_hash:
            continue
        if att.outcome in {"parse_failed", "compile_failed", "panel_failed", "execution_failed"}:
            continue
        seen.add(att.formula_hash)

    derived = max(1, len(seen)) if seen else 0
    if declared_family_size is not None and declared_family_size < derived:
        raise ValueError(
            f"declared family size ({declared_family_size}) cannot be less than derived ({derived})"
        )
    effective = max(derived, declared_family_size or 0)
    if effective == 0:
        effective = 1
    return FamilySizeResult(
        policy_version=policy_version,
        derived_family_size=derived,
        evaluated_formula_hashes=tuple(sorted(seen)),
        declared_family_size=declared_family_size,
        effective_family_size=effective,
    )


def is_correction_stale(
    *,
    family_size_at_evaluation: int,
    current_derived_size: int,
) -> bool:
    return current_derived_size > family_size_at_evaluation
