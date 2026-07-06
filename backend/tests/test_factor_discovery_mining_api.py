"""API route tests for mining sessions."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config
from engines.quant_db import init_quant_db


@pytest.fixture
def client(isolated_backend_env, monkeypatch):
    init_quant_db()
    monkeypatch.setenv("FACTOR_DISCOVERY_LOOP_ENABLED", "false")
    config.FACTOR_DISCOVERY_LOOP_ENABLED.set(False)
    from fastapi.testclient import TestClient
    from main import app

    return TestClient(app)


def test_mining_routes_disabled_by_default(client):
    resp = client.get("/api/v2/research/factor-discovery/mining/sessions")
    assert resp.status_code == 503
