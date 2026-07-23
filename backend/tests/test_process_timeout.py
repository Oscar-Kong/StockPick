"""Process-isolation timeouts must terminate hung workers and accept large payloads."""
from __future__ import annotations

import sys
import time
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.process_timeout import run_with_process_timeout


def _sleep_then_return(seconds: float) -> str:
    """Top-level target so spawn can pickle it."""
    time.sleep(seconds)
    return "done"


def _return_large_bytes(nbytes: int) -> bytes:
    return b"x" * int(nbytes)


def _return_ohlc_frame(n_symbols: int, n_rows: int = 126) -> pd.DataFrame:
    """Yahoo-shaped multi-ticker frame (group_by=ticker layout approx)."""
    dates = pd.date_range("2025-01-01", periods=n_rows, freq="B")
    arrays = [
        [f"S{i}" for i in range(n_symbols) for _ in range(6)],
        ["Open", "High", "Low", "Close", "Adj Close", "Volume"] * n_symbols,
    ]
    columns = pd.MultiIndex.from_arrays(arrays)
    data = np.random.default_rng(0).random((n_rows, n_symbols * 6))
    return pd.DataFrame(data, index=dates, columns=columns)


def _raise_before_return() -> str:
    raise RuntimeError("child boom")


def test_run_with_process_timeout_returns_quickly_on_success():
    assert run_with_process_timeout(_sleep_then_return, 0.05, timeout=5.0) == "done"


def test_run_with_process_timeout_terminates_hung_worker():
    started = time.monotonic()
    with pytest.raises(TimeoutError):
        run_with_process_timeout(_sleep_then_return, 5.0, timeout=0.4)
    elapsed = time.monotonic() - started
    assert elapsed < 2.5, f"hung process waited {elapsed:.2f}s (expected < 2.5s)"


def test_run_with_process_timeout_large_bytes_payload():
    payload = run_with_process_timeout(_return_large_bytes, 1_000_000, timeout=15.0)
    assert isinstance(payload, bytes)
    assert len(payload) == 1_000_000


def test_run_with_process_timeout_large_dataframe_payload():
    frame = run_with_process_timeout(_return_ohlc_frame, 40, 126, timeout=15.0)
    assert isinstance(frame, pd.DataFrame)
    assert frame.shape[0] == 126
    assert frame.shape[1] == 40 * 6


def test_run_with_process_timeout_child_crash():
    with pytest.raises(RuntimeError, match="child boom"):
        run_with_process_timeout(_raise_before_return, timeout=5.0)


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
