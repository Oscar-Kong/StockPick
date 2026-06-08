"""Phase 4 unit tests — sizing math and risk deductions (no ta import)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engines.risk.unified import _check_deductions
from engines.scoring.data_quality import dq_multiplier


def test_conviction_sizing_formula():
    """Mirror PositionSizingEngine medium example from architecture §9.6."""
    w_max = 0.08
    score = 78.0
    c = max(0.0, min(1.0, (score - 50.0) / 50.0))
    w_base = w_max * (c**2)
    phi = dq_multiplier(82)
    m_risk = max(0.4, min(1.0, 1.0 - 0.006 * 25))
    w1 = w_base * phi * m_risk
    w2 = w1 * ((1.0 - 0.6) ** 0.5)
    assert abs(w_base * 100 - 2.51) < 0.2
    assert 1.0 < w2 * 100 < 2.0


def test_earnings_deduction():
    d = _check_deductions(
        days_until_earnings=5,
        governance_score=70,
        data_quality_score=80,
        valuation_warnings=[],
        openbb_flags=[],
    )
    assert any(x["category"] == "earnings_soon" for x in d)


def test_governance_deduction():
    d = _check_deductions(
        days_until_earnings=None,
        governance_score=30,
        data_quality_score=80,
        valuation_warnings=[],
        openbb_flags=[],
    )
    assert any(x["category"] == "governance" for x in d)


if __name__ == "__main__":
    test_conviction_sizing_formula()
    test_earnings_deduction()
    test_governance_deduction()
    print("quant v2 phase4 tests passed")
