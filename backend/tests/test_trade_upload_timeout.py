"""Trade upload must not hang when prediction / decision side-effects stall."""
from __future__ import annotations

import time
from unittest.mock import patch

from fastapi.testclient import TestClient


def test_trade_upload_survives_hung_prediction(isolated_backend_env, monkeypatch):
    monkeypatch.setenv("TRADE_UPLOAD_PREDICTION_TIMEOUT_SECONDS", "0.3")
    monkeypatch.setenv("TRADE_UPLOAD_DECISION_TIMEOUT_SECONDS", "0.3")

    import config

    monkeypatch.setattr(config, "TRADE_UPLOAD_PREDICTION_TIMEOUT_SECONDS", 0.3, raising=False)
    monkeypatch.setattr(config, "TRADE_UPLOAD_DECISION_TIMEOUT_SECONDS", 0.3, raising=False)

    def hang_prediction(*_a, **_k):
        time.sleep(5)
        return None

    with patch("api.routes_trades.record_prediction_for_trade", side_effect=hang_prediction):
        with patch(
            "services.portfolio_snapshot_service.apply_manual_trade_to_portfolio",
            return_value={"imported": 1, "skipped": 0, "holdings_count": 1, "message": "ok"},
        ):
            with patch(
                "services.portfolio_snapshot_service.evaluate_portfolio_sync_result",
                return_value=(True, "ok"),
            ):
                from main import app

                client = TestClient(app)
                started = time.monotonic()
                res = client.post(
                    "/trades/upload",
                    data={
                        "symbol": "AAPL",
                        "side": "long",
                        "entry_time": "2026-07-18T15:00:00Z",
                        "entry_price": "200",
                        "quantity": "1",
                        "notes": "timeout-guard",
                    },
                )
                elapsed = time.monotonic() - started

    assert res.status_code == 200, res.text
    assert elapsed < 2.5, f"upload hung for {elapsed:.2f}s"
    body = res.json()
    assert body["symbol"] == "AAPL"
    assert body["quantity"] == 1.0


def test_manual_trade_decision_timeout_does_not_block_ledger_sync(isolated_backend_env, monkeypatch):
    monkeypatch.setattr(
        "config.TRADE_UPLOAD_DECISION_TIMEOUT_SECONDS",
        0.2,
        raising=False,
    )

    def hang_decision(*_a, **_k):
        time.sleep(5)
        raise AssertionError("should have timed out")

    from services.portfolio_snapshot_service import apply_manual_trade_to_portfolio
    from datetime import datetime

    with patch(
        "services.portfolio_decision_service.run_stored_portfolio_decision",
        side_effect=hang_decision,
    ):
        started = time.monotonic()
        result = apply_manual_trade_to_portfolio(
            trade_id=999001,
            symbol="AAPL",
            side="long",
            entry_time=datetime(2026, 7, 18, 15, 0, 0),
            entry_price=200.0,
            quantity=1.0,
            notes="decision-timeout",
        )
        elapsed = time.monotonic() - started

    assert result is not None
    assert result.get("imported", 0) >= 0
    assert "decision_error" in result
    assert "timed out" in str(result["decision_error"]).lower()
    assert elapsed < 2.0, f"decision path hung for {elapsed:.2f}s"
