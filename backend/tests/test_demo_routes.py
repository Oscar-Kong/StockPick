"""Parameterized demo-mode guards for state-changing routes."""
from __future__ import annotations

import pytest

DISABLED_POST_ROUTES = [
    ("/brokerage/import/robinhood-csv", "post", {}),
    ("/brokerage/buying-power", "post", {"data": {"cash": "100"}}),
    ("/brokerage/validate/robinhood-csv", "post", {}),
    ("/trades/manual", "post", {"json": {"symbol": "AAPL", "side": "long", "entry_time": "2024-01-02T15:00:00", "entry_price": 1, "quantity": 1}}),
    ("/settings/apis", "patch", {"json": {"updates": {"SCHEDULER_ENABLED": True}}}),
    ("/settings/apis/reset", "post", {"json": {}}),
    ("/data/scheduler/run", "post", {}),
    ("/data/scheduler/refresh-quotes", "post", {}),
    ("/data/scheduler/refresh-fundamentals", "post", {}),
    ("/data/scheduler/refresh-listing-master", "post", {}),
    ("/data/refresh", "post", {}),
    ("/home/refresh", "post", {}),
    ("/api/v2/jobs/ic-panel", "post", {}),
    ("/api/v2/jobs/rebalance", "post", {}),
    ("/api/v2/jobs/enqueue/quant_daily_jobs", "post", {}),
    ("/lean/export", "post", {"json": {"bucket": "penny", "symbols": ["AAPL"]}}),
    ("/ml/alpha/ingest", "post", {"json": {"bucket": "penny", "items": []}}),
    ("/portfolio/daily-decision/run", "post", {}),
]


@pytest.mark.parametrize("path,method,kwargs", DISABLED_POST_ROUTES)
def test_demo_disabled_routes(demo_client, path, method, kwargs):
    if path.endswith("robinhood-csv"):
        kwargs = {"files": {"file": ("x.csv", b"a,b\n", "text/csv")}}

    caller = getattr(demo_client, method)
    r = caller(path, **kwargs)
    assert r.status_code in (403, 429), r.text
    detail = r.json().get("detail", {})
    if isinstance(detail, dict):
        assert detail.get("error") in ("DEMO_ACTION_DISABLED", "DEMO_LIMIT_EXCEEDED", "HTTP_ERROR", "VALIDATION_ERROR")


def test_demo_health_not_rate_limited(demo_client):
    for _ in range(5):
        r = demo_client.get("/health")
        assert r.status_code == 200


def test_demo_read_routes_ok(demo_client):
    for path in ("/health", "/health/ready", "/portfolio/current", "/settings/apis"):
        r = demo_client.get(path)
        assert r.status_code == 200, path
