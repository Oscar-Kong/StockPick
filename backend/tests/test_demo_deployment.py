"""Deployment and public demo mode tests."""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from utils import demo_guard


def test_health_lightweight(demo_client):
    r = demo_client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["demo_mode"] is True
    assert body["database"] == "available"
    assert "version" in body
    assert "FINNHUB_API_KEY" not in r.text
    assert body.get("finnhub_configured") is None


def test_health_ready(demo_client):
    r = demo_client.get("/health/ready")
    assert r.status_code == 200
    assert r.json()["database"] == "available"


def test_demo_seed_idempotent(demo_client):
    r1 = demo_client.get("/portfolio/current")
    assert r1.status_code == 200
    body1 = r1.json()
    assert body1.get("is_demo_data") is True
    assert len(body1.get("holdings") or []) >= 3

    r2 = demo_client.get("/portfolio/current")
    assert r2.status_code == 200
    assert len(r2.json().get("holdings") or []) == len(body1.get("holdings") or [])


def test_csv_import_disabled(demo_client):
    r = demo_client.post(
        "/brokerage/import/robinhood-csv",
        files={"file": ("test.csv", b"symbol,quantity\nAAPL,1\n", "text/csv")},
    )
    assert r.status_code == 403
    detail = r.json()["detail"]
    assert detail["error"] == "DEMO_ACTION_DISABLED"


def test_trade_journal_write_disabled(demo_client):
    payload = {
        "symbol": "AAPL",
        "side": "long",
        "entry_time": "2024-01-02T15:00:00",
        "entry_price": 100,
        "quantity": 1,
    }
    r = demo_client.post("/trades/manual", json=payload)
    assert r.status_code == 403
    assert r.json()["detail"]["error"] == "DEMO_ACTION_DISABLED"


def test_settings_patch_disabled(demo_client):
    r = demo_client.patch("/settings/apis", json={"updates": {"SCHEDULER_ENABLED": True}})
    assert r.status_code == 403


def test_scheduler_admin_disabled(demo_client):
    r = demo_client.post("/data/scheduler/run")
    assert r.status_code == 403


def test_v2_job_enqueue_disabled(demo_client):
    r = demo_client.post("/api/v2/jobs/enqueue/quant_daily_jobs")
    assert r.status_code == 403


def test_scan_limit_validation(monkeypatch):
    import config
    from models.schemas import ScanOptions

    monkeypatch.setattr(config, "DEMO_MODE", True)
    monkeypatch.setattr(config, "DEMO_MAX_SCAN_SYMBOLS", 10)
    capped = demo_guard.enforce_scan_options(ScanOptions(max_results=50))
    assert capped.max_results == 10


def test_backtest_symbol_limit(monkeypatch):
    import config

    monkeypatch.setattr(config, "DEMO_MODE", True)
    monkeypatch.setattr(config, "DEMO_MAX_BACKTEST_SYMBOLS", 3)
    with pytest.raises(HTTPException) as exc:
        demo_guard.enforce_backtest_symbols(["A", "B", "C", "D"])
    assert exc.value.status_code == 400


def test_cors_allowed_origin(demo_client):
    r = demo_client.get("/health", headers={"Origin": "http://localhost:18730"})
    assert r.status_code == 200
    assert r.headers.get("access-control-allow-origin") == "http://localhost:18730"


def test_cors_blocked_origin(demo_client):
    r = demo_client.get("/health", headers={"Origin": "https://evil.example"})
    assert r.status_code == 200
    assert r.headers.get("access-control-allow-origin") != "https://evil.example"


def test_api_settings_redacted_in_demo(demo_client):
    r = demo_client.get("/settings/apis")
    assert r.status_code == 200
    body = r.json()
    assert body.get("read_only") is True
    for group in body.get("groups", []):
        for item in group.get("items", []):
            assert item.get("requires_key") is None
