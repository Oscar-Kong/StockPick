"""Launch idempotency tests."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.factor_discovery.errors import IdempotencyConflictError
from services.factor_discovery.idempotency import launch_payload_hash
from services.factor_discovery.repositories import FactorDiscoveryRunRepository
from tests.fixtures.factor_discovery.persistence_helpers import enable_factor_discovery, seed_family_and_definition
from tests.fixtures.factor_discovery.validation.validation_panel_builder import build_validation_context


def test_launch_payload_hash_stable(isolated_backend_env):
    ctx = build_validation_context()
    h1 = launch_payload_hash(
        factor_id="f1",
        factor_version="1.0.0",
        research_family_id="fam",
        snapshot_request_identity=None,
        snapshot_id=None,
        period_split=ctx["period_split"],
        validation_config=ctx["validation_config"],
    )
    h2 = launch_payload_hash(
        factor_id="f1",
        factor_version="1.0.0",
        research_family_id="fam",
        snapshot_request_identity=None,
        snapshot_id=None,
        period_split=ctx["period_split"],
        validation_config=ctx["validation_config"],
    )
    assert h1 == h2


def test_run_idempotency_same_payload(isolated_backend_env):
    _, definition, ctx = seed_family_and_definition()
    repo = FactorDiscoveryRunRepository()
    payload = launch_payload_hash(
        factor_id=definition.factor_id,
        factor_version=definition.version,
        research_family_id="ffam_test",
        snapshot_request_identity=None,
        snapshot_id=None,
        period_split=ctx["period_split"],
        validation_config=ctx["validation_config"],
    )
    r1 = repo.create(
        factor_id=definition.factor_id,
        factor_version=definition.version,
        research_family_id="ffam_test",
        status="running",
        idempotency_key="idem-1",
        launch_payload_hash=payload,
        created_by="test",
    )
    r2 = repo.create(
        factor_id=definition.factor_id,
        factor_version=definition.version,
        research_family_id="ffam_test",
        status="running",
        idempotency_key="idem-1",
        launch_payload_hash=payload,
        created_by="test",
    )
    assert r1 == r2


def test_run_idempotency_payload_mismatch(isolated_backend_env):
    _, definition, ctx = seed_family_and_definition()
    repo = FactorDiscoveryRunRepository()
    repo.create(
        factor_id=definition.factor_id,
        factor_version=definition.version,
        research_family_id="ffam_x",
        status="running",
        idempotency_key="idem-2",
        launch_payload_hash="sha256:aaa",
        created_by="test",
    )
    with pytest.raises(IdempotencyConflictError):
        repo.create(
            factor_id=definition.factor_id,
            factor_version=definition.version,
            research_family_id="ffam_x",
            status="running",
            idempotency_key="idem-2",
            launch_payload_hash="sha256:bbb",
            created_by="test",
        )
