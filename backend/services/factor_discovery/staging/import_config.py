"""Load and validate staging import configuration files."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

import config as app_config
from services.factor_discovery.errors import FactorDiscoveryError

ALLOWED_SCHEMA_VERSIONS = frozenset({"factor-universe-import-v1", "factor-snapshot-materialize-v1", "factor-staging-run-v1"})
ALLOWED_CONFLICT_POLICIES = frozenset({"reject", "keep_existing", "replace_staging_bucket"})
ALLOWED_ENVIRONMENTS = frozenset({"staging", "test", "development"})


@dataclass(frozen=True)
class UniverseImportConfig:
    schema_version: str
    environment: str
    universe_id: str
    source_id: str
    source_version: str
    input_format: str
    input_path: Path
    symbol_mapping_version: str
    calendar_id: str
    effective_date_policy: str
    conflict_policy: str
    actor: str
    reason: str
    research_start: str | None
    research_end: str | None
    config_hash: str

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "environment": self.environment,
            "universe_id": self.universe_id,
            "source_id": self.source_id,
            "source_version": self.source_version,
            "input_format": self.input_format,
            "input_path": str(self.input_path),
            "symbol_mapping_version": self.symbol_mapping_version,
            "calendar_id": self.calendar_id,
            "effective_date_policy": self.effective_date_policy,
            "conflict_policy": self.conflict_policy,
            "actor": self.actor,
            "reason": self.reason,
            "research_start": self.research_start,
            "research_end": self.research_end,
            "config_hash": self.config_hash,
        }


def _config_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return f"sha256:{hashlib.sha256(canonical.encode()).hexdigest()[:16]}"


def _validate_path_under_root(path: Path) -> Path:
    root = Path(getattr(app_config, "FACTOR_RESEARCH_STAGING_INPUT_ROOT", "") or "")
    resolved = path.resolve()
    if not resolved.exists():
        raise FactorDiscoveryError("STAGING_CONFIG_INPUT_MISSING", str(resolved))
    if root:
        root_resolved = root.resolve()
        if not str(resolved).startswith(str(root_resolved)):
            raise FactorDiscoveryError("STAGING_INPUT_PATH_ESCAPE", "input path outside staging input root")
    return resolved


def load_universe_import_config(config_path: Path) -> UniverseImportConfig:
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise FactorDiscoveryError("STAGING_CONFIG_INVALID", "config must be a mapping")
    allowed_keys = {
        "schema_version",
        "environment",
        "universe_id",
        "source_id",
        "source_version",
        "input_format",
        "input_path",
        "symbol_mapping_version",
        "calendar_id",
        "effective_date_policy",
        "conflict_policy",
        "actor",
        "reason",
        "research_start",
        "research_end",
        "security_types",
        "exchanges",
    }
    unknown = set(raw) - allowed_keys
    if unknown:
        raise FactorDiscoveryError("STAGING_CONFIG_UNKNOWN_FIELDS", ",".join(sorted(unknown)))

    schema_version = str(raw["schema_version"])
    if schema_version not in ALLOWED_SCHEMA_VERSIONS:
        raise FactorDiscoveryError("STAGING_CONFIG_SCHEMA", schema_version)

    environment = str(raw["environment"]).lower()
    if environment not in ALLOWED_ENVIRONMENTS:
        raise FactorDiscoveryError("STAGING_CONFIG_ENVIRONMENT", environment)

    conflict_policy = str(raw.get("conflict_policy", "reject"))
    if conflict_policy not in ALLOWED_CONFLICT_POLICIES:
        raise FactorDiscoveryError("STAGING_CONFIG_CONFLICT_POLICY", conflict_policy)

    input_rel = str(raw["input_path"])
    input_root = Path(getattr(app_config, "FACTOR_RESEARCH_STAGING_INPUT_ROOT", "") or "")
    input_path = _validate_path_under_root((input_root / input_rel) if input_root else Path(input_rel))

    if not raw.get("research_start") or not raw.get("research_end"):
        raise FactorDiscoveryError("STAGING_CONFIG_MISSING_DATES", "research_start and research_end required")

    payload = {k: raw[k] for k in sorted(raw) if k != "input_path"}
    payload["input_path"] = str(input_path)

    return UniverseImportConfig(
        schema_version=schema_version,
        environment=environment,
        universe_id=str(raw["universe_id"]),
        source_id=str(raw["source_id"]),
        source_version=str(raw["source_version"]),
        input_format=str(raw.get("input_format", "interval_csv")),
        input_path=input_path,
        symbol_mapping_version=str(raw.get("symbol_mapping_version", "symbol_mapping_v1")),
        calendar_id=str(raw.get("calendar_id", "us_equity_observed_union_v1")),
        effective_date_policy=str(raw.get("effective_date_policy", "inclusive_start_inclusive_end")),
        conflict_policy=conflict_policy,
        actor=str(raw["actor"]),
        reason=str(raw["reason"]),
        research_start=raw.get("research_start"),
        research_end=raw.get("research_end"),
        config_hash=_config_hash(payload),
    )


def require_staging_mutations_enabled() -> None:
    if not bool(getattr(app_config, "FACTOR_DISCOVERY_STAGING_ENABLED", False)):
        raise FactorDiscoveryError("STAGING_NOT_ENABLED", "FACTOR_DISCOVERY_STAGING_ENABLED must be true for mutations")
