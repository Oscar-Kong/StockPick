"""Launch payload hashing for Factor Discovery idempotency."""
from __future__ import annotations

import hashlib
import json

from engines.factor.discovery.validation_hashing import validation_config_hash
from engines.factor.discovery.validation_models import FactorValidationConfig
from models.schemas_factor_discovery import DiscoveryPeriodSplit


def launch_payload_hash(
    *,
    factor_id: str,
    factor_version: str,
    research_family_id: str,
    snapshot_request_identity: str | None,
    snapshot_id: str | None,
    period_split: DiscoveryPeriodSplit,
    validation_config: FactorValidationConfig,
) -> str:
    payload = {
        "factor_id": factor_id,
        "factor_version": factor_version,
        "research_family_id": research_family_id,
        "snapshot_request": snapshot_request_identity,
        "snapshot_id": snapshot_id,
        "period_split": period_split.model_dump(mode="json"),
        "validation_config_hash": validation_config_hash(validation_config),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return f"sha256:{hashlib.sha256(canonical.encode()).hexdigest()}"
