"""Quant Lab API contract tests — explicit enabled/disabled/degraded scenarios."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.fixtures.quant_lab_fixtures import build_cointegrated_panel, seed_quant_lab_demo


@pytest.fixture
def client(isolated_backend_env):
    try:
        from fastapi.testclient import TestClient
        from main import app

        return TestClient(app)
    except RuntimeError as exc:
        if "httpx" in str(exc):
            pytest.skip("httpx not installed")
        raise


@pytest.fixture
def quant_lab_client(client, monkeypatch):
    """V2 + feedback enabled with seeded evidence."""
    import config

    monkeypatch.setattr(config, "SCORE_ENGINE_V2_ENABLED", True, raising=False)
    monkeypatch.setattr(config, "TRADE_FEEDBACK_ENABLED", True, raising=False)
    monkeypatch.setattr(config, "DEMO_MODE", False, raising=False)
    monkeypatch.setattr("api.routes_v2.SCORE_ENGINE_V2_ENABLED", True)
    monkeypatch.setattr("api.routes_v2.TRADE_FEEDBACK_ENABLED", True)
    monkeypatch.setattr("api.routes_research.DEMO_MODE", False)
    monkeypatch.setenv("SCORE_ENGINE_V2_ENABLED", "true")
    monkeypatch.setenv("TRADE_FEEDBACK_ENABLED", "true")
    monkeypatch.setenv("DEMO_MODE", "false")
    seed_quant_lab_demo(sleeve="penny")
    return client


def _assert_disabled_503(r, *, feature: str):
    assert r.status_code == 503, r.text
    body = r.json()
    detail = body.get("detail", body)
    if isinstance(detail, dict):
        assert detail.get("error") or detail.get("message")
    else:
        assert feature in str(detail).lower() or "disabled" in str(detail).lower()


def test_factors_performance_enabled_contract(quant_lab_client):
    r = quant_lab_client.get("/api/v2/factors/performance?sleeve=penny")
    assert r.status_code == 200, r.text
    body = r.json()
    assert "as_of_date" in body
    assert isinstance(body["factors"], list)
    assert len(body["factors"]) >= 1
    assert "by_horizon" in body


def test_factors_performance_disabled_contract(client, monkeypatch):
    monkeypatch.setattr("api.routes_v2.SCORE_ENGINE_V2_ENABLED", False)
    r = client.get("/api/v2/factors/performance?sleeve=penny")
    _assert_disabled_503(r, feature="score")


def test_predictions_enabled_contract(quant_lab_client):
    r = quant_lab_client.get("/api/v2/predictions?limit=10")
    assert r.status_code == 200, r.text
    body = r.json()
    assert isinstance(body["predictions"], list)
    assert len(body["predictions"]) >= 1
    row = body["predictions"][0]
    assert "symbol" in row and "created_at" in row
    assert "outcome" in row


def test_feedback_summary_enabled_contract(quant_lab_client):
    r = quant_lab_client.get("/api/v2/feedback/summary")
    assert r.status_code == 200, r.text
    body = r.json()
    for key in ("outcomes_count", "snapshots_count", "recent_outcomes", "recent_snapshots"):
        assert key in body


def test_feedback_disabled_contract(client, monkeypatch):
    monkeypatch.setattr("api.routes_v2.TRADE_FEEDBACK_ENABLED", False)
    r = client.get("/api/v2/feedback/summary")
    _assert_disabled_503(r, feature="feedback")


def test_weights_contract(quant_lab_client):
    r = quant_lab_client.get("/api/v2/weights/penny")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["sleeve"] == "penny"
    assert "weights" in body


def test_audit_contract(quant_lab_client):
    r = quant_lab_client.get("/api/v2/audit?limit=5")
    assert r.status_code == 200, r.text
    assert isinstance(r.json()["events"], list)


def test_factors_admin_contract(quant_lab_client):
    r = quant_lab_client.get("/api/v2/factors/admin?sleeve=penny")
    assert r.status_code == 200, r.text
    assert isinstance(r.json()["factors"], list)


def test_scheduler_status_contract(quant_lab_client):
    r = quant_lab_client.get("/data/scheduler/status")
    assert r.status_code == 200, r.text
    body = r.json()
    assert "enabled" in body
    assert isinstance(body["recent_jobs"], list)


def test_walk_forward_validation(quant_lab_client):
    r = quant_lab_client.post(
        "/research/walk-forward",
        json={
            "sleeve": "penny",
            "start_date": "2026-01-01",
            "end_date": "2025-01-01",
            "forward_horizons": [20],
        },
    )
    assert r.status_code == 400


def test_walk_forward_latest_with_seed(quant_lab_client):
    r = quant_lab_client.get("/research/walk-forward/latest?sleeve=penny")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["available"] is True
    assert body["run_id"] == "wf_test_001"


def test_pairs_latest_with_seed(quant_lab_client):
    r = quant_lab_client.get("/research/pairs/latest")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["available"] is True
    assert body["run_id"] == "pairs_test_001"


def test_pairs_research_real_service(quant_lab_client):
    panel = build_cointegrated_panel()
    with patch("services.pairs_research_service.load_aligned_closes") as mock_load:
        mock_load.return_value = (panel, ["AAA", "BBB", "CCC", "DDD", "EEE", "FFF"], [])
        r = quant_lab_client.post(
            "/research/pairs",
            json={"symbols": ["AAA", "BBB", "CCC", "DDD"], "lookback_period": "1y"},
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["pairs_evaluated"] >= 1
    assert body.get("run_id")
    latest = quant_lab_client.get("/research/pairs/latest").json()
    assert latest["available"] is True
    assert latest.get("run_id")


def test_quant_lab_evidence_contract(quant_lab_client):
    r = quant_lab_client.get("/api/v2/quant-lab/evidence?sleeve=penny")
    assert r.status_code == 200, r.text
    body = r.json()
    for key in ("factor_ic", "walk_forward", "predictions", "pairs", "jobs"):
        card = body[key]
        assert "available" in card
        assert "trust_indicator" in card
    assert body["factor_ic"]["available"] is True
    assert body["walk_forward"]["available"] is True
    assert body["pairs"]["available"] is True
    assert "validation_copy" in body


def test_version_contract(quant_lab_client):
    r = quant_lab_client.get("/api/v2/version")
    assert r.status_code == 200, r.text
    body = r.json()
    assert "strategy_version" in body
    assert "factor_model_version" in body


def test_evidence_empty_database(client, monkeypatch):
    import config

    monkeypatch.setattr(config, "SCORE_ENGINE_V2_ENABLED", True, raising=False)
    monkeypatch.setattr(config, "TRADE_FEEDBACK_ENABLED", True, raising=False)
    r = client.get("/api/v2/quant-lab/evidence?sleeve=penny")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["factor_ic"]["available"] is False
    assert body["walk_forward"]["available"] is False
    assert body["pairs"]["available"] is False


def test_pairs_empty_latest(client):
    r = client.get("/research/pairs/latest")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["available"] is False
    assert body["reason"]
