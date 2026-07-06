"""API contract tests for Factor Discovery mining workspace (Phase 8B)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config
from engines.quant_db import init_quant_db
from tests.fixtures.factor_discovery.mining.helpers import enable_mining, mining_session_request


@pytest.fixture
def mining_client(isolated_backend_env, monkeypatch):
    init_quant_db()
    enable_mining(monkeypatch)
    from main import app

    return TestClient(app)


def test_mining_readiness_endpoint(mining_client):
    resp = mining_client.get("/api/v2/research/factor-discovery/mining/readiness")
    assert resp.status_code == 200
    body = resp.json()
    assert "factor_discovery_enabled" in body
    assert body["bounded_auto_ready"] is False
    assert body["no_sealed_access"] is True
    assert body["no_production_integration"] is True


def test_mutation_requires_state_version(mining_client):
    created = mining_client.post(
        "/api/v2/research/factor-discovery/mining/sessions",
        json=mining_session_request().model_dump(mode="json"),
    )
    assert created.status_code == 200
    sid = created.json()["session_id"]
    resp = mining_client.post(
        f"/api/v2/research/factor-discovery/mining/sessions/{sid}/authorize",
        json={"actor": "tester", "reason": "test"},
    )
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "MISSING_STATE_VERSION"


def test_stale_state_version_returns_409(mining_client):
    created = mining_client.post(
        "/api/v2/research/factor-discovery/mining/sessions",
        json=mining_session_request().model_dump(mode="json"),
    )
    sid = created.json()["session_id"]
    ok = mining_client.post(
        f"/api/v2/research/factor-discovery/mining/sessions/{sid}/authorize",
        json={"actor": "tester", "reason": "ok", "expected_state_version": 0},
    )
    assert ok.status_code == 200
    assert ok.json()["state_version"] == 1
    conflict = mining_client.post(
        f"/api/v2/research/factor-discovery/mining/sessions/{sid}/start",
        json={"actor": "tester", "expected_state_version": 0},
    )
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "STATE_VERSION_CONFLICT"


def test_mutation_envelope_shape(mining_client):
    created = mining_client.post(
        "/api/v2/research/factor-discovery/mining/sessions",
        json=mining_session_request().model_dump(mode="json"),
    )
    sid = created.json()["session_id"]
    resp = mining_client.post(
        f"/api/v2/research/factor-discovery/mining/sessions/{sid}/authorize",
        json={"actor": "tester", "reason": "authorize for envelope test", "expected_state_version": 0},
    )
    body = resp.json()
    for key in (
        "session_id",
        "status",
        "state_version",
        "pending_reviews",
        "allowed_actions",
        "budget_summary",
    ):
        assert key in body
    assert "can_authorize" in body["allowed_actions"]
    assert "can_reject_hypothesis" in body["allowed_actions"]


def test_session_detail_allowed_actions(mining_client):
    created = mining_client.post(
        "/api/v2/research/factor-discovery/mining/sessions",
        json=mining_session_request().model_dump(mode="json"),
    )
    sid = created.json()["session_id"]
    detail = mining_client.get(f"/api/v2/research/factor-discovery/mining/sessions/{sid}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["allowed_actions"]["can_authorize"] is True
    assert body["allowed_actions"]["can_start"] is False
    assert "action_disabled_reasons" in body
    assert body["pending_reviews"]["hypotheses"] == 0


def test_list_sessions_enriched(mining_client):
    created = mining_client.post(
        "/api/v2/research/factor-discovery/mining/sessions",
        json=mining_session_request().model_dump(mode="json"),
    )
    assert created.status_code == 200
    listed = mining_client.get("/api/v2/research/factor-discovery/mining/sessions")
    assert listed.status_code == 200
    items = listed.json()["items"]
    assert len(items) >= 1
    assert "pending_reviews" in items[0]
    assert "research_objective" in items[0]
