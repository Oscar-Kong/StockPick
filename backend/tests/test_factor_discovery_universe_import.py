"""Universe import tests."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config
from data.db_engine import get_engine
from engines.quant_models import UniversePit
from services.factor_discovery.staging.import_config import load_universe_import_config
from services.factor_discovery.staging.import_universe import FactorDiscoveryStagingUniverseImporter
from services.factor_discovery.staging.universe_audit import FactorDiscoveryUniverseAuditService
from sqlalchemy.orm import Session
from tests.fixtures.factor_discovery.staging.helpers import seed_staging_fixture


def _write_interval_csv(root: Path) -> Path:
    p = root / "universe" / "test_intervals.csv"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        "symbol,effective_start,effective_end,exchange,eligibility_reason\n"
        "AAA,2020-01-02,2020-01-08,NASDAQ,test\n"
        "BBB,2020-01-02,2020-01-06,NASDAQ,test\n"
        "CCC,2020-01-04,2020-01-08,NASDAQ,test\n",
        encoding="utf-8",
    )
    return p


def _write_config(root: Path, csv_rel: str) -> Path:
    cfg = {
        "schema_version": "factor-universe-import-v1",
        "environment": "staging",
        "universe_id": "test_universe_v1",
        "source_id": "test_source_v1",
        "source_version": "1",
        "input_format": "interval_csv",
        "input_path": csv_rel,
        "symbol_mapping_version": "symbol_mapping_v1",
        "calendar_id": "us_equity_observed_union_v1",
        "effective_date_policy": "inclusive_start_inclusive_end",
        "conflict_policy": "replace_staging_bucket",
        "research_start": "2020-01-02",
        "research_end": "2020-01-10",
        "actor": "test",
        "reason": "unit test import",
    }
    path = root / "universe" / "test_import.yaml"
    path.write_text(yaml.dump(cfg), encoding="utf-8")
    return path


def test_dry_run_import(isolated_backend_env, tmp_path, monkeypatch):
    seed_staging_fixture(variant="valid")
    monkeypatch.setattr(config, "FACTOR_RESEARCH_STAGING_INPUT_ROOT", str(tmp_path), raising=False)
    _write_interval_csv(tmp_path)
    cfg_path = _write_config(tmp_path, "universe/test_intervals.csv")
    cfg = load_universe_import_config(cfg_path)
    report = FactorDiscoveryStagingUniverseImporter().import_from_config(cfg, dry_run=True)
    assert report.status == "dry_run_ok"
    assert report.daily_rows_generated > 0
    assert report.config_hash.startswith("sha256:")


def test_commit_import(isolated_backend_env, tmp_path, monkeypatch):
    seed_staging_fixture(variant="valid")
    monkeypatch.setattr(config, "FACTOR_RESEARCH_STAGING_INPUT_ROOT", str(tmp_path), raising=False)
    monkeypatch.setattr(config, "FACTOR_DISCOVERY_STAGING_ENABLED", True, raising=False)
    _write_interval_csv(tmp_path)
    cfg_path = _write_config(tmp_path, "universe/test_intervals.csv")
    cfg = load_universe_import_config(cfg_path)
    report = FactorDiscoveryStagingUniverseImporter().import_from_config(cfg, dry_run=False)
    assert report.status == "committed"
    audit = FactorDiscoveryUniverseAuditService().audit()
    assert audit.unique_dates >= 2
    assert audit.entry_events >= 1


def test_import_requires_staging_flag(isolated_backend_env, tmp_path, monkeypatch):
    seed_staging_fixture(variant="valid")
    monkeypatch.setattr(config, "FACTOR_RESEARCH_STAGING_INPUT_ROOT", str(tmp_path), raising=False)
    monkeypatch.setattr(config, "FACTOR_DISCOVERY_STAGING_ENABLED", False, raising=False)
    _write_interval_csv(tmp_path)
    cfg_path = _write_config(tmp_path, "universe/test_intervals.csv")
    cfg = load_universe_import_config(cfg_path)
    from services.factor_discovery.errors import FactorDiscoveryError

    with pytest.raises(FactorDiscoveryError):
        FactorDiscoveryStagingUniverseImporter().import_from_config(cfg, dry_run=False)
