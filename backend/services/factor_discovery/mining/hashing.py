"""Deterministic hashing for mining session configuration."""
from __future__ import annotations

import hashlib
import json

from engines.factor.discovery.validation_hashing import validation_config_hash
from engines.factor.discovery.validation_models import FactorValidationConfig
from models.schemas_factor_discovery import DiscoveryPeriodSplit
from services.factor_discovery.llm.models import NormalizedFactorResearchRequest
from services.factor_discovery.mining.models import (
    FactorMiningAutoPolicy,
    FactorMiningBudgetPolicy,
    FactorMiningPausePolicy,
    FactorMiningStoppingPolicy,
)


def _canonical_hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return f"sha256:{hashlib.sha256(canonical.encode()).hexdigest()}"


def period_hash(period_split: DiscoveryPeriodSplit) -> str:
    return _canonical_hash(period_split.model_dump(mode="json"))


def pause_policy_hash(policy: FactorMiningPausePolicy) -> str:
    return _canonical_hash(policy.model_dump(mode="json"))


def stopping_policy_hash(policy: FactorMiningStoppingPolicy) -> str:
    return _canonical_hash(policy.model_dump(mode="json"))


def budget_policy_hash(policy: FactorMiningBudgetPolicy) -> str:
    return _canonical_hash(policy.model_dump(mode="json"))


def session_config_hash(
    *,
    research_family_id: str,
    normalized_request: NormalizedFactorResearchRequest,
    session_mode: str,
    snapshot_id: str | None,
    snapshot_identity_hash: str | None,
    data_provider_id: str,
    data_source_policy_id: str,
    period_split: DiscoveryPeriodSplit,
    validation_config: FactorValidationConfig,
    pause_policy: FactorMiningPausePolicy,
    stopping_policy: FactorMiningStoppingPolicy,
    budget_policy: FactorMiningBudgetPolicy,
    auto_policy: FactorMiningAutoPolicy,
) -> str:
    return _canonical_hash(
        {
            "research_family_id": research_family_id,
            "normalized_request": normalized_request.model_dump(mode="json"),
            "session_mode": session_mode,
            "snapshot_id": snapshot_id,
            "snapshot_identity_hash": snapshot_identity_hash,
            "data_provider_id": data_provider_id,
            "data_source_policy_id": data_source_policy_id,
            "period_hash": period_hash(period_split),
            "validation_config_hash": validation_config_hash(validation_config),
            "pause_policy_hash": pause_policy_hash(pause_policy),
            "stopping_policy_hash": stopping_policy_hash(stopping_policy),
            "budget_hash": budget_policy_hash(budget_policy),
            "auto_policy": auto_policy.model_dump(mode="json"),
        }
    )


def event_log_hash(events: list[dict]) -> str:
    semantic = [
        {
            "event_type": e.get("event_type"),
            "previous_state": e.get("previous_state"),
            "new_state": e.get("new_state"),
            "reason_code": e.get("reason_code"),
            "lineage_id": e.get("lineage_id"),
            "candidate_id": e.get("candidate_id"),
            "run_id": e.get("run_id"),
        }
        for e in events
    ]
    return _canonical_hash({"events": semantic})
