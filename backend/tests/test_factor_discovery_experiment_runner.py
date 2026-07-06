"""Experiment runner end-to-end and failure path tests."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from models.schemas_factor_discovery import FactorLifecycleStatus
from services.factor_discovery.errors import FactorDiscoveryError
from services.factor_discovery.experiment_runner import FactorDiscoveryExperimentRunner, FactorDiscoveryRunRequest
from services.factor_discovery.repositories import FactorDiscoveryRunRepository
from tests.fixtures.factor_discovery.persistence_helpers import enable_factor_discovery, seed_family_and_definition


def test_runner_fails_draft_factor(enabled, isolated_backend_env, monkeypatch):
    enable_factor_discovery(monkeypatch)
    family_id, definition, ctx = seed_family_and_definition(status=FactorLifecycleStatus.DRAFT)
    runner = FactorDiscoveryExperimentRunner(fixture_builder=lambda: ctx["panel"])
    with pytest.raises(FactorDiscoveryError) as exc:
        runner.run(
            FactorDiscoveryRunRequest(
                experiment_id=None,
                job_id=None,
                factor_id=definition.factor_id,
                factor_version=definition.version,
                research_family_id=family_id,
                period_split=ctx["period_split"],
                validation_config=ctx["validation_config"],
                created_by="test",
            )
        )
    assert exc.value.code == "FACTOR_NOT_COMPILED"


def test_runner_persists_failed_run(enabled, isolated_backend_env, monkeypatch):
    enable_factor_discovery(monkeypatch)
    family_id, definition, ctx = seed_family_and_definition(status=FactorLifecycleStatus.DRAFT)
    runner = FactorDiscoveryExperimentRunner(fixture_builder=lambda: ctx["panel"])
    with pytest.raises(FactorDiscoveryError):
        runner.run(
            FactorDiscoveryRunRequest(
                experiment_id=None,
                job_id=None,
                factor_id=definition.factor_id,
                factor_version=definition.version,
                research_family_id=family_id,
                period_split=ctx["period_split"],
                validation_config=ctx["validation_config"],
                created_by="test",
            )
        )
    from data.db_engine import get_engine
    from engines.factor_discovery_models import FactorDiscoveryRun
    from sqlalchemy.orm import Session

    with Session(get_engine()) as session:
        rows = session.query(FactorDiscoveryRun).filter(FactorDiscoveryRun.factor_id == definition.factor_id).all()
    assert rows
    assert rows[-1].status == "failed"
    assert rows[-1].error_code == "FACTOR_NOT_COMPILED"


@pytest.fixture
def enabled(monkeypatch):
    enable_factor_discovery(monkeypatch)
