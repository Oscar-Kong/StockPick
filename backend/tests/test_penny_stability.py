"""Behavior tests for penny stability and entry-risk decisions."""
from __future__ import annotations

import math

import pandas as pd

from scoring.penny_stability import assess_penny_stability


def _history(*, dollar_volume: float, latest_gap_pct: float = 0.0) -> pd.DataFrame:
    closes = [2.0 + index * 0.01 for index in range(25)]
    opens = list(closes)
    opens[-1] = closes[-2] * (1.0 + latest_gap_pct / 100.0)
    volume = [dollar_volume / close for close in closes]
    return pd.DataFrame(
        {
            "open": opens,
            "high": [close * 1.02 for close in closes],
            "low": [close * 0.98 for close in closes],
            "close": closes,
            "volume": volume,
        }
    )


def test_thin_extended_candidate_is_high_risk_even_with_strong_alpha():
    decision = assess_penny_stability(
        _history(dollar_volume=150_000.0, latest_gap_pct=12.0),
        alpha_score=91.0,
    )

    assert decision.stability.classification == "rejected"
    assert "insufficient_dollar_liquidity" in decision.stability.hard_gates
    assert decision.entry.classification == "no_chase"
    assert decision.to_metrics_dict()["decision_state"] == "no_trade"
    assert decision.alpha_score == 91.0


def test_liquid_orderly_candidate_keeps_alpha_and_can_be_buy():
    decision = assess_penny_stability(
        _history(dollar_volume=8_000_000.0),
        alpha_score=84.0,
    )

    assert decision.stability.classification in {"normal", "stable"}
    assert decision.stability.hard_gates == ()
    assert decision.entry.classification in {"normal", "acceptable"}
    assert decision.to_metrics_dict()["decision_state"] == "watch"


def test_zero_volume_history_returns_rejected_decision_without_error():
    decision = assess_penny_stability(
        _history(dollar_volume=0.0),
        alpha_score=95.0,
    )

    assert decision.stability.classification == "rejected"
    assert decision.stability.raw["median_dollar_volume_20d"] == 0.0
    assert math.isfinite(decision.stability.raw["amihud_20d"])
    assert decision.to_metrics_dict()["decision_state"] == "no_trade"


def test_large_gap_down_is_risky_but_not_labeled_no_chase():
    decision = assess_penny_stability(
        _history(dollar_volume=8_000_000.0, latest_gap_pct=-12.0),
        alpha_score=84.0,
    )

    assert decision.entry.classification == "wait"
    assert "large_gap_down" in decision.entry.reasons


def test_malformed_ohlcv_is_explainably_rejected():
    history = _history(dollar_volume=8_000_000.0)
    history.loc[history.index[-1], "close"] = float("nan")

    decision = assess_penny_stability(history, alpha_score=90.0)

    assert decision.stability.hard_gates == ("invalid_history",)
    assert decision.to_metrics_dict()["decision_state"] == "no_trade"
