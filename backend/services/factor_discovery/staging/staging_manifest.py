"""Versioned staging manifest for extended Phase 9B.2 runs."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import config as app_config
from services.factor_discovery.staging.environment import database_identity_hash, resolve_staging_contract, staging_config_hash
from services.factor_discovery.staging.policies import STAGING_VALIDATION_CONFIG

EXTENDED_STAGING_MANIFEST_SCHEMA = "factor_extended_staging_manifest_v1"
FACTOR_REGISTRY_VERSION = "factor_registry_v1"
LABEL_DEFINITION = "forward_return_next_session_v1"


def _utcnow() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat()


def manifest_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return f"sha256:{hashlib.sha256(canonical.encode()).hexdigest()[:16]}"


@dataclass
class ExtendedStagingManifest:
    schema_version: str = EXTENDED_STAGING_MANIFEST_SCHEMA
    staging_run_id: str = ""
    code_version: str | None = None
    database_fingerprint: str = ""
    data_provider_id: str = ""
    active_sleeves: list[str] = field(default_factory=list)
    start_date: str = ""
    end_date: str = ""
    pit_universe_version: str = ""
    factor_registry_version: str = FACTOR_REGISTRY_VERSION
    label_definition: str = LABEL_DEFINITION
    forward_horizon_sessions: int = 20
    cost_assumptions_bps: int = 10
    random_seed: int = 42
    configuration_hash: str = ""
    environment_flags: dict = field(default_factory=dict)
    matrix_spec: dict = field(default_factory=dict)
    generated_at: str = field(default_factory=_utcnow)

    def identity_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "staging_run_id": self.staging_run_id,
            "code_version": self.code_version,
            "database_fingerprint": self.database_fingerprint,
            "data_provider_id": self.data_provider_id,
            "active_sleeves": sorted(self.active_sleeves),
            "start_date": self.start_date,
            "end_date": self.end_date,
            "pit_universe_version": self.pit_universe_version,
            "factor_registry_version": self.factor_registry_version,
            "label_definition": self.label_definition,
            "forward_horizon_sessions": self.forward_horizon_sessions,
            "cost_assumptions_bps": self.cost_assumptions_bps,
            "random_seed": self.random_seed,
            "configuration_hash": self.configuration_hash,
            "environment_flags": self.environment_flags,
            "matrix_spec": self.matrix_spec,
        }

    def to_dict(self) -> dict[str, Any]:
        body = self.identity_payload()
        body["generated_at"] = self.generated_at
        body["manifest_hash"] = manifest_hash(self.identity_payload())
        return body


def build_extended_staging_manifest(
    *,
    staging_run_id: str,
    sleeves: list[str],
    start_date: str,
    end_date: str,
    pit_universe_version: str,
    matrix_spec: dict,
    random_seed: int = 42,
    code_version: str | None = None,
) -> ExtendedStagingManifest:
    contract = resolve_staging_contract()
    env_flags = {
        "FACTOR_DISCOVERY_STAGING_ENABLED": bool(getattr(app_config, "FACTOR_DISCOVERY_STAGING_ENABLED", False)),
        "FACTOR_RESEARCH_DATA_PROVIDER": str(app_config.FACTOR_RESEARCH_DATA_PROVIDER),
        "FACTOR_DISCOVERY_ENABLED": bool(app_config.FACTOR_DISCOVERY_ENABLED),
        "APP_ENV": str(getattr(app_config, "APP_ENV", "development")),
    }
    cfg_hash = staging_config_hash()
    return ExtendedStagingManifest(
        staging_run_id=staging_run_id,
        code_version=code_version or contract.git_commit,
        database_fingerprint=database_identity_hash(),
        data_provider_id=contract.data_provider_id,
        active_sleeves=sleeves,
        start_date=start_date,
        end_date=end_date,
        pit_universe_version=pit_universe_version,
        forward_horizon_sessions=int(STAGING_VALIDATION_CONFIG["primary_horizon"]),
        cost_assumptions_bps=int(STAGING_VALIDATION_CONFIG["transaction_cost_bps"]),
        random_seed=random_seed,
        configuration_hash=cfg_hash,
        environment_flags=env_flags,
        matrix_spec=matrix_spec,
    )
