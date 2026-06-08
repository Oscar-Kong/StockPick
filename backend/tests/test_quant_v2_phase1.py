"""Phase 1 unit tests — no market data / ta dependencies."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engines.factor.catalog import active_factor_catalog, signal_name_to_factor_id
from engines.scoring.data_quality import dq_multiplier


def test_factor_catalog_covers_sleeves():
    catalog = active_factor_catalog()
    assert set(catalog) == {"penny", "medium", "compounder"}
    for sleeve, specs in catalog.items():
        w = sum(s.weight for s in specs)
        assert 0.99 <= w <= 1.01, f"{sleeve} weights sum to {w}"


def test_signal_name_mapping():
    fid = signal_name_to_factor_id("penny", "5-day momentum")
    assert fid == "penny_momentum_5d"


def test_dq_multiplier_monotonic():
    assert dq_multiplier(80) == 1.0
    assert dq_multiplier(None) == 0.92
    assert dq_multiplier(30) < dq_multiplier(60)


if __name__ == "__main__":
    test_factor_catalog_covers_sleeves()
    test_signal_name_mapping()
    test_dq_multiplier_monotonic()
    print("quant v2 phase1 tests passed")
