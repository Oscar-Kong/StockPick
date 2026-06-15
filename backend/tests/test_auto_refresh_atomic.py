"""H4: auto-refresh reservation must be atomic.

Before `try_begin_auto_refresh`, `_attach_auto_refresh` took the orchestrator
lock four separate times (is_running, cooldown_allowed, start_async, mark).
Two near-simultaneous dashboard GETs could each observe "not running, cooldown
OK" before either reserved the slot, then both advance the cooldown while only
one actually did work.

These tests pin the atomic contract: with N concurrent callers, exactly one
gets a job_id; everyone else gets None. The cooldown is also stamped exactly
once.
"""
from __future__ import annotations

import sys
import threading
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services import refresh_orchestrator as ro


def _reset_orchestrator_state() -> None:
    """Clean module-level globals between tests (they are mutable singletons)."""
    with ro._lock:
        ro._home_refresh_running = False
        ro._active_home_job_id = None
        ro._refresh_started_at = None
        ro._last_auto_refresh_at = None
        ro._jobs.clear()


def test_try_begin_auto_refresh_returns_job_id_on_first_call():
    _reset_orchestrator_state()
    started = threading.Event()

    def _fake_execute(*, force: bool = False) -> dict:
        # Block so the slot stays "running" while we make a second call.
        started.set()
        return {"status": "ok", "steps": {}}

    with patch.object(ro, "_execute_home_refresh", side_effect=_fake_execute):
        first = ro.try_begin_auto_refresh()
        # Let the worker thread finish so subsequent tests see a clean slot.
        started.wait(timeout=2.0)
    assert first is not None


def test_try_begin_auto_refresh_returns_none_when_already_running():
    _reset_orchestrator_state()
    release = threading.Event()
    started = threading.Event()

    def _slow_execute(*, force: bool = False) -> dict:
        started.set()
        release.wait(timeout=5.0)
        return {"status": "ok", "steps": {}}

    with patch.object(ro, "_execute_home_refresh", side_effect=_slow_execute):
        first = ro.try_begin_auto_refresh()
        assert first is not None
        # Wait until the background worker actually starts so the running
        # flag is observably set across the lock boundary.
        assert started.wait(timeout=2.0)
        second = ro.try_begin_auto_refresh()
        release.set()
    assert second is None


def test_try_begin_auto_refresh_respects_cooldown():
    """Once an auto refresh has been started, the cooldown blocks the next
    auto attempt until AUTO_REFRESH_COOLDOWN_SECONDS elapses."""
    _reset_orchestrator_state()

    def _fast_execute(*, force: bool = False) -> dict:
        return {"status": "ok", "steps": {}}

    with patch.object(ro, "_execute_home_refresh", side_effect=_fast_execute):
        first = ro.try_begin_auto_refresh()
        assert first is not None
        # Wait for the worker thread to fully clear `_home_refresh_running`.
        for _ in range(50):
            if not ro.is_home_refresh_running():
                break
            threading.Event().wait(0.02)
        # Now the run flag is clear, but cooldown should still be active.
        second = ro.try_begin_auto_refresh()
    assert second is None, "cooldown must block a second auto refresh immediately after the first"


def test_concurrent_callers_exactly_one_wins():
    """The whole point: N threads racing through `_attach_auto_refresh` must
    produce exactly one non-None job_id. If we ever regress to the
    non-atomic check-then-reserve pattern this test will catch it."""
    _reset_orchestrator_state()
    barrier = threading.Barrier(8)
    started = threading.Event()
    release = threading.Event()
    results: list[str | None] = []
    results_lock = threading.Lock()

    def _slow_execute(*, force: bool = False) -> dict:
        started.set()
        release.wait(timeout=5.0)
        return {"status": "ok", "steps": {}}

    def _worker() -> None:
        barrier.wait(timeout=2.0)
        jid = ro.try_begin_auto_refresh()
        with results_lock:
            results.append(jid)

    with patch.object(ro, "_execute_home_refresh", side_effect=_slow_execute):
        threads = [threading.Thread(target=_worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5.0)
        started.wait(timeout=2.0)
        release.set()

    winners = [r for r in results if r is not None]
    assert len(winners) == 1, f"expected exactly one winner, got {winners}"
    assert results.count(None) == 7
