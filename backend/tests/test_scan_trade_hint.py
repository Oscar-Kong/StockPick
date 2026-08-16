"""Tests for scan buy/wait trade hints."""
from __future__ import annotations

from models.schemas import RiskLevel
from services.scan_trade_hint import attach_trade_hint_to_metrics, compute_scan_trade_hint


def test_high_score_penny_has_buy_bias():
    hint = compute_scan_trade_hint(
        score=82.0,
        sleeve="penny",
        risk_level=RiskLevel.medium,
        data_quality_score=75.0,
    )
    assert hint["buy_pct"] > hint["wait_pct"]
    assert hint["recommendation"] in ("strong_buy", "buy")


def test_low_score_skews_wait():
    hint = compute_scan_trade_hint(
        score=42.0,
        sleeve="penny",
        risk_level=RiskLevel.high,
        data_quality_score=60.0,
    )
    assert hint["wait_pct"] > hint["buy_pct"]
    assert hint["recommendation"] in ("hold", "avoid", "watch")


def test_provider_limited_caps_recommendation():
    hint = compute_scan_trade_hint(
        score=78.0,
        sleeve="penny",
        risk_level=RiskLevel.medium,
        provider_limited=True,
    )
    assert hint["recommendation"] == "watch"
    assert "Partial provider data" in hint["trade_hint_reason"]


def test_attach_trade_hint_to_metrics():
    metrics = attach_trade_hint_to_metrics(
        {"earnings_soon": True},
        score=70.0,
        sleeve="compounder",
        risk_level=RiskLevel.low,
        data_quality_score=80.0,
    )
    assert metrics["buy_pct"] + metrics["wait_pct"] == 100.0
    assert metrics["recommendation"]
    assert metrics["trade_hint_reason"]


def test_penny_trade_hint_uses_raw_volume_ratio_in_reason():
    hint = compute_scan_trade_hint(
        score=72.0,
        sleeve="penny",
        risk_level=RiskLevel.high,
        data_quality_score=75.0,
        metrics={
            "relative_volume_ratio": 3.2,
            "relative_volume_score": 100.0,
            "atr_percent": 7.4,
            "average_dollar_volume_20d": 4_800_000,
        },
    )
    reason = hint["trade_hint_reason"]
    assert "3.2x" in reason
    assert "100/100" in reason or "100" in reason
    assert "7.4%" in reason
    assert "4.8M" in reason


def test_strong_alpha_with_poor_entry_is_watch():
    hint = compute_scan_trade_hint(
        score=91.0,
        sleeve="penny",
        risk_level=RiskLevel.high,
        data_quality_score=80.0,
        metrics={
            "stability_classification": "stable",
            "entry_risk_score": 84.0,
            "entry_risk_classification": "no_chase",
            "entry_risk_reasons": ["extreme_latest_gap"],
        },
    )

    assert hint["recommendation"] == "watch"
    assert hint["wait_pct"] > hint["buy_pct"]
    assert "poor entry" in hint["trade_hint_reason"].lower()


def test_rejected_stability_is_no_trade_not_watch():
    hint = compute_scan_trade_hint(
        score=91.0,
        sleeve="penny",
        risk_level=RiskLevel.high,
        metrics={"stability_classification": "rejected", "decision_state": "no_trade"},
    )

    assert hint["recommendation"] == "avoid"


def test_alpha_bias_is_separate_from_final_watch_decision():
    hint = compute_scan_trade_hint(
        score=82.0,
        sleeve="penny",
        risk_level=RiskLevel.medium,
        data_quality_score=80.0,
        metrics={
            "stability_classification": "stable",
            "entry_risk_classification": "normal",
            "decision_state": "watch",
        },
    )

    assert hint["alpha_bias"] == "bullish"
    assert hint["decision_state"] == "watch"
    assert hint["recommendation"] == "watch"
