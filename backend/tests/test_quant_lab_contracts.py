"""Quant Lab API contract tests — response shapes expected by frontend."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture
def client():
    try:
        from fastapi.testclient import TestClient
        from main import app

        return TestClient(app)
    except RuntimeError as exc:
        if "httpx" in str(exc):
            pytest.skip("httpx not installed")
        raise


def _skip_503(r):
    if r.status_code == 503:
        pytest.skip(r.json().get("detail", "feature disabled"))


def test_factors_performance_contract(client):
    r = client.get("/api/v2/factors/performance?sleeve=medium")
    _skip_503(r)
    assert r.status_code == 200
    body = r.json()
    assert "as_of_date" in body
    assert "factors" in body and isinstance(body["factors"], list)
    assert "by_horizon" in body
    assert "by_regime" in body
    assert "by_sector" in body


def test_predictions_contract(client):
    r = client.get("/api/v2/predictions?limit=5")
    _skip_503(r)
    assert r.status_code == 200
    body = r.json()
    assert "predictions" in body and isinstance(body["predictions"], list)
    if body["predictions"]:
        row = body["predictions"][0]
        assert "id" in row and "symbol" in row and "created_at" in row
        assert "outcome" in row


def test_feedback_summary_contract(client):
    r = client.get("/api/v2/feedback/summary")
    _skip_503(r)
    assert r.status_code == 200
    body = r.json()
    for key in ("outcomes_count", "snapshots_count", "recent_outcomes", "recent_snapshots"):
        assert key in body


def test_weights_contract(client):
    r = client.get("/api/v2/weights/medium")
    _skip_503(r)
    assert r.status_code == 200
    body = r.json()
    assert "sleeve" in body and "weights" in body


def test_audit_contract(client):
    r = client.get("/api/v2/audit?limit=5")
    assert r.status_code == 200
    body = r.json()
    assert "events" in body and isinstance(body["events"], list)


def test_factors_admin_contract(client):
    r = client.get("/api/v2/factors/admin?sleeve=medium")
    _skip_503(r)
    assert r.status_code == 200
    body = r.json()
    assert "factors" in body and isinstance(body["factors"], list)


def test_scheduler_status_contract(client):
    r = client.get("/data/scheduler/status")
    assert r.status_code == 200
    body = r.json()
    assert "enabled" in body
    assert "recent_jobs" in body and isinstance(body["recent_jobs"], list)


def test_walk_forward_validation(client):
    r = client.post(
        "/research/walk-forward",
        json={
            "sleeve": "medium",
            "start_date": "2026-01-01",
            "end_date": "2025-01-01",
            "forward_horizons": [20],
        },
    )
    assert r.status_code == 400


def test_pairs_research_contract(client):
    from unittest.mock import patch

    mock_body = {
        "research_only": True,
        "lookback_period": "1y",
        "symbols_requested": ["AAPL", "MSFT"],
        "symbols_used": ["AAPL", "MSFT"],
        "pairs": [],
        "pairs_evaluated": 1,
        "pairs_returned": 0,
        "cointegrated_count": 0,
        "statsmodels_available": False,
        "notes": ["mocked for contract test"],
    }
    with patch("api.routes_research.run_pairs_research", return_value=mock_body):
        r = client.post(
            "/research/pairs",
            json={"symbols": ["AAPL", "MSFT"], "lookback_period": "1y"},
        )
    assert r.status_code == 200
    body = r.json()
    for key in (
        "research_only",
        "pairs",
        "pairs_evaluated",
        "pairs_returned",
        "cointegrated_count",
        "statsmodels_available",
        "notes",
    ):
        assert key in body
    assert isinstance(body["pairs"], list)
    assert isinstance(body["notes"], list)


def test_version_contract(client):
    r = client.get("/api/v2/version")
    assert r.status_code == 200
    body = r.json()
    assert "strategy_version" in body
    assert "factor_model_version" in body


def test_walk_forward_latest_contract(client):
    r = client.get("/research/walk-forward/latest?sleeve=medium")
    assert r.status_code == 200
    body = r.json()
    assert "available" in body
    assert "trust_indicator" in body
    assert body["id"] == "walk_forward"


def test_pairs_latest_contract(client):
    r = client.get("/research/pairs/latest")
    assert r.status_code == 200
    body = r.json()
    assert body["available"] is False
    assert body["reason"]
    assert body["id"] == "pairs"


def test_quant_lab_evidence_contract(client):
    r = client.get("/api/v2/quant-lab/evidence?sleeve=medium")
    assert r.status_code == 200
    body = r.json()
    for key in ("factor_ic", "walk_forward", "predictions", "pairs", "jobs"):
        assert key in body
        assert "available" in body[key]
        assert "trust_indicator" in body[key]
    assert "validation_copy" in body
