"""Phase 6 unit tests — trade feedback math (no heavy imports)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engines.feedback.predictions import (
    expected_return_from_score,
    factor_attribution,
    horizon_days_for_sleeve,
    infer_sleeve,
)


def test_expected_return_mapping():
    assert expected_return_from_score(80, "penny") > 0
    assert expected_return_from_score(40, "penny") < 0
    assert horizon_days_for_sleeve("penny") == 14


def test_factor_attribution():
    factors = [
        {"factor_id": "a", "norm_score": 0.8},
        {"factor_id": "b", "norm_score": 0.2},
    ]
    attr = factor_attribution(factors, error_pct=5.0)
    assert abs(sum(attr.values()) - 5.0) < 0.01


def test_infer_sleeve_tags():
    assert infer_sleeve("AAPL", ["penny", "momentum"]) == "penny"


if __name__ == "__main__":
    test_expected_return_mapping()
    test_factor_attribution()
    test_infer_sleeve_tags()
    print("quant v2 phase6 tests passed")
