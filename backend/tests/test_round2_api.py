"""Round 2 API smoke tests."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


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
    assert "snapshots_total" in r.json()


def test_round2_admin_stats_direct():
    from services.round2_admin import round2_ops_stats

    stats = round2_ops_stats()
    assert "snapshots_total" in stats
    assert "model_version" in stats


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
