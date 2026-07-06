"""Analyze API accepts legacy medium bucket query (maps to penny)."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture
def client(isolated_backend_env):
    from fastapi.testclient import TestClient
    from main import app

    return TestClient(app)


def test_analyze_route_accepts_legacy_medium_bucket(client):
    payload = {
        "symbol": "TEST",
        "assigned_bucket": "penny",
        "price": 10.0,
        "score": 55.0,
        "risk_level": "medium",
        "summary": "test",
        "signals": [],
        "metrics": {},
        "valuation_warnings": [],
        "earnings_date": None,
        "days_until_earnings": None,
        "earnings_soon": False,
        "data_quality_score": 80,
        "reconcile": {},
        "technicals": {},
        "bucket_fit": {"scores": {}, "best_bucket": "penny"},
        "alerts": [],
        "ohlc": [],
        "fundamentals": {},
    }
    with patch(
        "api.routes_analyze._run_with_timeout",
        return_value=payload,
    ):
        r = client.get("/analyze/TEST?bucket=medium")
    assert r.status_code == 200, r.text
    assert r.json()["assigned_bucket"] == "penny"
