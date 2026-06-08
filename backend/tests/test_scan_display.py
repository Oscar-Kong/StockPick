"""Tests for scan display price return metrics."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.scan_display import price_return_metrics


def test_price_return_metrics():
    # 22 closes: start 100, end 110 (+10% vs 21 bars ago), +1% vs prior day
    closes = [100.0] * 20 + [108.9, 110.0]
    df = pd.DataFrame({"date": pd.date_range("2025-01-01", periods=22), "close": closes})
    m = price_return_metrics(df)
    assert m["change_pct_1d"] == 1.01
    assert m["change_pct_1w"] == 10.0
    assert m["change_pct_1m"] == 10.0


if __name__ == "__main__":
    test_price_return_metrics()
    print("scan_display tests passed")
