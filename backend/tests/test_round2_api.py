"""Round 2 API smoke tests."""
from __future__ import annotations

from unittest.mock import patch


def _client():
    try:
        from fastapi.testclient import TestClient
        from main import app

        return TestClient(app)
    except RuntimeError as exc:
        if "httpx" in str(exc):
            return None
        raise


def test_v2_score_shape():
    client = _client()
    if client is None:
        return
    mock_score = {
        "symbol": "AAPL",
        "sleeve": "medium",
        "score": 72.5,
        "market_regime": "neutral",
        "risk_level": "medium",
        "summary": "Mock summary",
        "factors": [],
        "signals": [],
        "attribution": {
            "raw_score": 72.5,
            "regime_mult": 1.0,
            "sector_tilt": 0.0,
            "dq_multiplier": 1.0,
            "openbb_delta": 0.0,
            "score_after_regime": 72.5,
            "score_after_dq": 72.5,
            "risk_deduction": 0.0,
            "final_score": 72.5,
        },
        "risk": {"risk_score": 30.0, "deduction_pts": 0.0, "items": []},
        "strategy_version": "test",
        "factor_model_version": "test",
    }
    with patch("api.routes_v2.build_v2_score", return_value=mock_score):
        r = client.get("/api/v2/score/AAPL?sleeve=medium")
    if r.status_code == 503:
        return
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("symbol") == "AAPL"
    assert "score" in body


def test_factor_performance_endpoint():
    client = _client()
    if client is None:
        return
    r = client.get("/api/v2/factors/performance")
    if r.status_code == 503:
        return
    assert r.status_code == 200
    body = r.json()
    assert "by_sector" in body
    assert "by_regime" in body


def test_round2_admin_stats():
    client = _client()
    if client is None:
        return
    r = client.get("/api/v2/admin/round2-stats")
    if r.status_code == 503:
        return
    assert r.status_code == 200
    body = r.json()
    assert "snapshots_total" in body
    assert isinstance(body["prediction_snapshots_enabled"], bool)


def test_round2_admin_stats_direct():
    from services.round2_admin import round2_ops_stats

    stats = round2_ops_stats()
    assert "snapshots_total" in stats
    assert "model_version" in stats
    assert isinstance(stats["prediction_snapshots_enabled"], bool)


def test_dcf_sensitivity_grid():
    from engines.valuation.engine import dcf_sensitivity_grid

    grid = dcf_sensitivity_grid(
        revenue=1e9,
        operating_margin=0.2,
        shares=100e6,
        revenue_cagr=0.1,
        wacc=0.1,
    )
    assert len(grid["wacc"]) == 4
    assert len(grid["values"]) == 4


if __name__ == "__main__":
    test_dcf_sensitivity_grid()
    test_round2_admin_stats_direct()
    test_v2_score_shape()
    test_factor_performance_endpoint()
    test_round2_admin_stats()
    print("round2 api tests ok")
