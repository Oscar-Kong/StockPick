"""API route tests for Factor Discovery LLM."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config
from engines.quant_db import init_quant_db
from tests.fixtures.factor_discovery.llm.helpers import (
    create_research_family,
    enable_llm_fixture,
    register_hypothesis_fixture,
)


@pytest.fixture
def client(isolated_backend_env):
    init_quant_db()
    from fastapi.testclient import TestClient
    from main import app

    return TestClient(app)


def test_llm_routes_disabled_by_default(client):
    r = client.post(
        "/api/v2/research/factor-discovery/llm/hypotheses/generate",
        json={"research_objective": "x", "research_family_id": "fam"},
    )
    assert r.status_code == 503


def test_generate_hypothesis_via_api(client, monkeypatch):
    enable_llm_fixture(monkeypatch)
    family_id = create_research_family()
    register_hypothesis_fixture()
    r = client.post(
        "/api/v2/research/factor-discovery/llm/hypotheses/generate",
        json={
            "research_objective": "momentum factor",
            "research_family_id": family_id,
            "candidate_count": 1,
            "actor": "api_tester",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "completed"
    assert body["candidate_ids"]
