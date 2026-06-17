"""Phase 3 unit tests — catalog v3, metrics, hard filters (no network)."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engines.factor.catalog_v3 import FACTOR_CATALOG_V3
from engines.filters.hard_filters import HARD_FILTER_TABLE, evaluate_hard_filters
from scoring.metrics import clip100
from screeners.base import CandidateContext


def test_v3_catalog_weights_sum():
    for sleeve, specs in FACTOR_CATALOG_V3.items():
        base = [s for s in specs if s.factor_id != f"{sleeve}_governance"]
        w = sum(s.weight for s in base)
        assert 0.99 <= w <= 1.01, f"{sleeve} base weights={w}"


def test_clip100_range():
    assert clip100(5, 0, 10) == 50.0
    assert clip100(0, 0, 10) == 0.0


def test_hard_filters_disabled_by_default():
    ctx = CandidateContext(symbol="TEST", price=3.0, info={}, history=pd.DataFrame())
    r = evaluate_hard_filters("penny", ctx)
    assert r.passed is True


def test_penny_delisting_filter(monkeypatch):
    import config
    import engines.filters.hard_filters as hf

    monkeypatch.setattr(config, "HARD_FILTERS_V3_ENABLED", True)
    monkeypatch.setattr(hf, "HARD_FILTERS_V3_ENABLED", True)
    dates = pd.date_range("2024-01-01", periods=35, freq="B")
    close = [0.8] * 35
    hist = pd.DataFrame(
        {
            "date": dates,
            "open": close,
            "high": close,
            "low": close,
            "close": close,
            "volume": [2_000_000] * 35,
        }
    )
    ctx = CandidateContext(symbol="TEST", price=0.8, info={}, history=hist)
    r = hf.evaluate_hard_filters("penny", ctx)
    assert r.passed is False
    assert any("delisting" in f for f in r.failed_rules)


def test_hard_filter_table_has_sleeves():
    sleeves = {r.sleeve for r in HARD_FILTER_TABLE}
    assert "penny" in sleeves
    assert "medium" in sleeves
    assert "compounder" in sleeves


if __name__ == "__main__":
    test_v3_catalog_weights_sum()
    test_clip100_range()
    test_hard_filters_disabled_by_default()
    test_hard_filter_table_has_sleeves()
    print("quant v2 phase3 tests passed (delisting test skipped in __main__)")
