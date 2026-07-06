"""Staging environment contract and identity helpers."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

import config as app_config


STAGING_ENVIRONMENT_NAMES = frozenset({"staging", "test", "development"})


@dataclass(frozen=True)
class StagingEnvironmentContract:
    environment_name: str
    database_identity_hash: str
    data_provider_id: str
    snapshot_root: str
    staging_enabled: bool
    input_root: str
    is_demo_mode: bool
    git_commit: str | None
    config_hash: str

    def to_dict(self) -> dict:
        return {
            "environment_name": self.environment_name,
            "database_identity_hash": self.database_identity_hash,
            "data_provider_id": self.data_provider_id,
            "snapshot_root": self.snapshot_root,
            "staging_enabled": self.staging_enabled,
            "input_root": self.input_root,
            "is_demo_mode": self.is_demo_mode,
            "git_commit": self.git_commit,
            "config_hash": self.config_hash,
        }


def _git_commit() -> str | None:
    try:
        root = Path(__file__).resolve().parents[3]
        out = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, stderr=subprocess.DEVNULL, text=True)
        return out.strip()[:12]
    except Exception:
        return None


def database_identity_hash() -> str:
    url = getattr(app_config, "DATABASE_URL", "") or "sqlite:default"
    # Never include credentials — hash only backend type + path fragment
    if "@" in url:
        backend = url.split("@", 1)[-1]
    else:
        backend = url.split("///")[-1] if "///" in url else url
    return f"sha256:{hashlib.sha256(backend.encode()).hexdigest()[:16]}"


def staging_config_hash() -> str:
    payload = {
        "FACTOR_DISCOVERY_STAGING_ENABLED": bool(getattr(app_config, "FACTOR_DISCOVERY_STAGING_ENABLED", False)),
        "FACTOR_RESEARCH_DATA_PROVIDER": str(app_config.FACTOR_RESEARCH_DATA_PROVIDER),
        "FACTOR_RESEARCH_SNAPSHOT_ROOT": str(getattr(app_config, "FACTOR_RESEARCH_SNAPSHOT_ROOT", "")),
        "FACTOR_DISCOVERY_ENABLED": bool(app_config.FACTOR_DISCOVERY_ENABLED),
        "APP_ENV": str(getattr(app_config, "APP_ENV", os.getenv("APP_ENV", "development"))),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return f"sha256:{hashlib.sha256(canonical.encode()).hexdigest()[:16]}"


def resolve_staging_contract() -> StagingEnvironmentContract:
    env_name = getattr(app_config, "APP_ENV", os.getenv("APP_ENV", "development")).strip().lower()
    demo = bool(getattr(app_config, "DEMO_MODE", False))
    return StagingEnvironmentContract(
        environment_name=env_name,
        database_identity_hash=database_identity_hash(),
        data_provider_id=app_config.FACTOR_RESEARCH_DATA_PROVIDER,
        snapshot_root=str(getattr(app_config, "FACTOR_RESEARCH_SNAPSHOT_ROOT", "")),
        staging_enabled=bool(getattr(app_config, "FACTOR_DISCOVERY_STAGING_ENABLED", False)),
        input_root=str(getattr(app_config, "FACTOR_RESEARCH_STAGING_INPUT_ROOT", "")),
        is_demo_mode=demo,
        git_commit=_git_commit(),
        config_hash=staging_config_hash(),
    )


def validate_staging_environment(*, allow_test: bool = False) -> tuple[bool, list[str]]:
    contract = resolve_staging_contract()
    blocking: list[str] = []
    if contract.environment_name not in STAGING_ENVIRONMENT_NAMES and not allow_test:
        blocking.append(f"unknown_environment:{contract.environment_name}")
    if contract.is_demo_mode:
        blocking.append("demo_mode_active")
    if app_config.FACTOR_RESEARCH_DATA_PROVIDER == "fixture" and getattr(app_config, "APP_ENV", "test") != "test":
        blocking.append("fixture_provider_outside_test")
    if not contract.staging_enabled and not allow_test:
        blocking.append("FACTOR_DISCOVERY_STAGING_ENABLED is false")
    return (len(blocking) == 0, blocking)
