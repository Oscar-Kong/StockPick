"""API contract tests for Factor Discovery Phase 9A review & evidence endpoints."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engines.quant_db import init_quant_db
from tests.fixtures.factor_discovery.mining.helpers import enable_mining, mining_session_request


@pytest.fixture
def mining_client(isolated_backend_env, monkeypatch):
    init_quant_db()
    enable_mining(monkeypatch)
    from main import app

    return TestClient(app)


def test_review_queue_shape(mining_client):
    resp = mining_client.get("/api/v2/research/factor-discovery/mining/review-queue")
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    assert "total" in body
    assert isinstance(body["items"], list)


def test_hypothesis_candidate_detail_not_found(mining_client):
    resp = mining_client.get("/api/v2/research/factor-discovery/candidates/hypotheses/missing-candidate")
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"]


def test_formula_candidate_detail_not_found(mining_client):
    resp = mining_client.get("/api/v2/research/factor-discovery/candidates/formulas/missing-candidate")
    assert resp.status_code == 404


def test_revision_candidate_detail_not_found(mining_client):
    resp = mining_client.get("/api/v2/research/factor-discovery/candidates/revisions/missing-candidate")
    assert resp.status_code == 404


def test_factor_registry_list_shape(mining_client):
    resp = mining_client.get("/api/v2/research/factor-discovery/factors")
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    assert "total" in body


def test_factor_registry_detail_not_found(mining_client):
    resp = mining_client.get("/api/v2/research/factor-discovery/factors/missing-factor")
    assert resp.status_code == 404


def test_validation_result_not_found(mining_client):
    resp = mining_client.get("/api/v2/research/factor-discovery/artifacts/missing-artifact/validation-result")
    assert resp.status_code == 404


def test_validation_result_by_run_not_found(mining_client):
    resp = mining_client.get("/api/v2/research/factor-discovery/runs/missing-run/validation-result")
    assert resp.status_code == 404


def test_session_integrity_endpoint(mining_client):
    created = mining_client.post(
        "/api/v2/research/factor-discovery/mining/sessions",
        json=mining_session_request().model_dump(mode="json"),
    )
    sid = created.json()["session_id"]
    resp = mining_client.get(f"/api/v2/research/factor-discovery/mining/sessions/{sid}/integrity")
    assert resp.status_code == 200
    body = resp.json()
    assert "integrity_ok" in body
