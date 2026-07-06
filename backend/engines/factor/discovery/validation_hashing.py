"""Deterministic hashing for Factor Discovery validation."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from engines.factor.discovery.validation_models import (
    VALIDATION_ENGINE_VERSION,
    FactorValidationConfig,
    SealedTestAccess,
)


def validation_config_hash(config: FactorValidationConfig) -> str:
    canonical = json.dumps(config.canonical_payload(), sort_keys=True, separators=(",", ":"))
    return f"sha256:{hashlib.sha256(canonical.encode()).hexdigest()}"


def validation_artifact_hash(
    *,
    formula_hash: str,
    plan_hash: str,
    execution_hash: str,
    outcome_hashes: dict[str, str],
    period_resolution_hash: str,
    validation_config_hash_value: str,
    sealed_opened: bool,
    sealed_access: SealedTestAccess | None = None,
) -> str:
    payload: dict[str, Any] = {
        "engine": VALIDATION_ENGINE_VERSION,
        "formula": formula_hash,
        "plan": plan_hash,
        "execution": execution_hash,
        "outcomes": dict(sorted(outcome_hashes.items())),
        "periods": period_resolution_hash,
        "config": validation_config_hash_value,
        "sealed_opened": sealed_opened,
    }
    if sealed_access is not None:
        payload["sealed_access"] = sealed_access.canonical_payload()
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return f"sha256:{hashlib.sha256(canonical.encode()).hexdigest()}"
