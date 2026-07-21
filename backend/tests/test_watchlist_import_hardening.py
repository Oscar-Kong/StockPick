"""Watchlist import reliability: timeouts, bucket coercion, serial analyze."""
from __future__ import annotations

import threading
import time
from unittest.mock import patch

from models.schemas import Bucket, RiskLevel, StockResult
from services.scoring_facade import _strategy_version_for
from services.scan_scoring import ScanScoreOutcome
from services.watchlist_scanner import analyze_symbol, import_to_watchlist


def test_watchlist_import_default_timeout_is_at_least_30s():
    from config import WATCHLIST_IMPORT_PER_SYMBOL_TIMEOUT_SECONDS

    assert WATCHLIST_IMPORT_PER_SYMBOL_TIMEOUT_SECONDS >= 30.0


def test_strategy_version_for_accepts_string_bucket():
    version = _strategy_version_for("compounder")
    assert isinstance(version, str) and version


def test_analyze_symbol_coerces_string_bucket(monkeypatch):
    """String buckets must not crash score_stage_b with AttributeError on .value."""
    from services import watchlist_scanner as ws

    fake = StockResult(
        symbol="AAPL",
        bucket=Bucket.compounder,
        price=100.0,
        score=50.0,
        signals=[],
        risk_level=RiskLevel.medium,
        summary="ok",
        metrics={},
    )
    calls: list[object] = []

    def capture_score(**kwargs):
        calls.append(kwargs.get("bucket"))
        return ScanScoreOutcome(
            score=50.0,
            signals=[],
            risk=RiskLevel.medium,
            summary="ok",
            metrics={},
            raw_score=50.0,
        )

    class FakeCtx:
        symbol = "AAPL"
        price = 100.0
        info = {"marketCap": 2e12, "_reconcile_quality": 80}
        history = None

    class FakeScreener:
        def hard_filter(self, ctx, options):
            return True

        def to_result(self, ctx, score, signals, risk, summary, metrics):
            return fake

    monkeypatch.setattr(ws, "build_candidate", lambda *a, **k: FakeCtx())
    monkeypatch.setattr(
        ws,
        "_SCREENERS",
        {Bucket.compounder: FakeScreener, Bucket.penny: FakeScreener},
    )
    monkeypatch.setattr(
        "services.scoring_facade.score_symbol_canonical",
        capture_score,
    )

    result, err = analyze_symbol("AAPL", "compounder")
    assert err is None
    assert result is not None
    assert calls and isinstance(calls[0], Bucket)


def test_import_to_watchlist_serializes_concurrent_analyzes():
    """Parallel import calls should not stampede analyze concurrently."""
    active = 0
    max_active = 0
    lock = threading.Lock()

    def slow_analyze(symbol, bucket_choice="auto"):
        nonlocal active, max_active
        with lock:
            active += 1
            max_active = max(max_active, active)
        time.sleep(0.15)
        with lock:
            active -= 1
        fake = StockResult(
            symbol=symbol.upper(),
            bucket=Bucket.compounder,
            price=10.0,
            score=40.0,
            signals=[],
            risk_level=RiskLevel.medium,
            summary="ok",
            metrics={},
        )
        return fake, None

    with patch("services.watchlist_scanner.analyze_symbol", side_effect=slow_analyze):
        with patch(
            "services.watchlist_scanner._save_result_to_watchlist",
            return_value={"notes": ""},
        ):
            barriers: list = []

            def worker(sym: str):
                barriers.append(
                    import_to_watchlist(sym, "compounder", per_symbol_timeout_seconds=5)
                )

            threads = [
                threading.Thread(target=worker, args=(s,)) for s in ("AAA", "BBB", "CCC")
            ]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=5)
            assert all(not t.is_alive() for t in threads)
            assert max_active == 1
            assert sum(1 for batch in barriers for row in batch if row.get("added")) == 3
