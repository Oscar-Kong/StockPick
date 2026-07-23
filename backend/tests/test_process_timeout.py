"""Process-isolation timeouts must terminate hung workers (not wait on shutdown)."""
from __future__ import annotations

import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.process_timeout import run_with_process_timeout


def _sleep_then_return(seconds: float) -> str:
    """Top-level target so spawn can pickle it."""
    time.sleep(seconds)
    return "done"


def test_run_with_process_timeout_returns_quickly_on_success():
    assert run_with_process_timeout(_sleep_then_return, 0.05, timeout=5.0) == "done"


def test_run_with_process_timeout_terminates_hung_worker():
    started = time.monotonic()
    with pytest.raises(TimeoutError):
        run_with_process_timeout(_sleep_then_return, 5.0, timeout=0.4)
    elapsed = time.monotonic() - started
    # Must not wait for the full 5s sleep after terminate.
    assert elapsed < 2.5, f"hung process waited {elapsed:.2f}s (expected < 2.5s)"


def test_yfinance_batch_returns_on_chunk_timeout_without_waiting():
    import data.yfinance_client as yf_mod

    started = time.monotonic()
    with (
        patch.object(yf_mod, "_import_yfinance", return_value=object()),
        patch(
            "utils.process_timeout.run_with_process_timeout",
            side_effect=TimeoutError("process timed out after 3s"),
        ),
    ):
        out = yf_mod.download_batch(
            ["AAA", "BBB"],
            period="6mo",
            max_runtime_seconds=30,
        )
    elapsed = time.monotonic() - started
    assert out == {}
    assert elapsed < 2.0
