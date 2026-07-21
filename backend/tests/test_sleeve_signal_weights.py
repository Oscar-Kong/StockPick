"""Stage B sleeve weights — legacy screeners must share the SleeveSignals table."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if "ta" not in sys.modules:
    _ta = MagicMock()
    sys.modules["ta"] = _ta
    sys.modules["ta.momentum"] = _ta.momentum
    sys.modules["ta.trend"] = _ta.trend
    sys.modules["ta.volatility"] = _ta.volatility

from engines.factor.catalog import FACTOR_CATALOG
from engines.factor.sleeve_signals import build_penny_signals
from models.schemas import Bucket
from screeners.base import CandidateContext
from screeners.penny import PennyScreener


def _ctx(symbol: str = "PENY") -> CandidateContext:
    dates = pd.date_range("2025-01-01", periods=60, freq="B")
    closes = [2.0 + i * 0.02 for i in range(60)]
    history = pd.DataFrame(
        {
            "date": dates,
            "open": closes,
            "high": [c + 0.05 for c in closes],
            "low": [c - 0.05 for c in closes],
            "close": closes,
            "volume": [2_000_000] * 60,
        }
    )
    return CandidateContext(
        symbol=symbol,
        price=closes[-1],
        info={"sector": "Technology", "marketCap": 80_000_000, "_reconcile_quality": 75.0},
        fundamentals={},
        history=history,
    )


@pytest.fixture
def scoring_stubs():
    """Stub legs so the test asserts weights, not TA/network behavior."""
    payload = {"score": 55.0, "stocktwits": 55.0}
    with (
        patch("engines.factor.sleeve_signals.combined_sentiment_score", return_value=payload),
        patch("screeners.penny.combined_sentiment_score", return_value=payload),
        patch("engines.factor.sleeve_signals.momentum_score", return_value=60.0),
        patch("engines.factor.sleeve_signals.volume_spike_score", return_value=65.0),
        patch("engines.factor.sleeve_signals.rsi_score", return_value=50.0),
        patch("engines.factor.sleeve_signals.volatility_fit_score", return_value=55.0),
        patch("screeners.penny.momentum_score", return_value=60.0),
        patch("screeners.penny.spread_proxy_score", return_value=40.0),
        patch(
            "engines.factor.openalpha_signals.append_openalpha_signals",
            side_effect=lambda sleeve, ctx, signals: signals,
        ),
        patch(
            "screeners.penny.compute_penny_liquidity_metrics",
            return_value=MagicMock(
                relative_volume_score=65.0,
                relative_volume_ratio=1.5,
                warnings=[],
                to_metrics_dict=lambda: {"relative_volume_score": 65.0},
            ),
        ),
        patch("screeners.penny.detect_penny_risk_warnings", return_value=[]),
        patch("screeners.penny_setup.classify_penny_setup", return_value=("momentum_burst", [])),
        patch.object(
            PennyScreener,
            "apply_regime",
            return_value=(70.0, {}),
        ),
    ):
        yield payload


def test_penny_screener_signal_weights_match_sleeve_signals(scoring_stubs):
    """Legacy PennyScreener.score must use the same legs/weights as build_penny_signals."""
    ctx = _ctx()
    expected = build_penny_signals(ctx)

    def _identity_prepare(self, ctx, signals):
        return signals

    with (
        patch("config.SLEEVE_FACTORS_V3_ENABLED", False),
        patch.object(PennyScreener, "prepare_signals", _identity_prepare),
    ):
        _, signals, _, _, _ = PennyScreener().score(ctx)

    by_name = {s.name: s.weight for s in signals if s.name in {e.name for e in expected}}
    for sig in expected:
        assert by_name[sig.name] == pytest.approx(sig.weight), (
            f"{sig.name}: screener={by_name.get(sig.name)} sleeve={sig.weight}"
        )
    assert "Liquidity/spread" not in {s.name for s in signals}


def test_penny_catalog_weights_match_sleeve_signals(scoring_stubs):
    """FACTOR_CATALOG penny static weights track build_penny_signals."""
    ctx = _ctx("CAT")
    signals = build_penny_signals(ctx)
    catalog = {spec.signal_name: spec.weight for spec in FACTOR_CATALOG["penny"]}
    for sig in signals:
        assert sig.name in catalog
        assert catalog[sig.name] == pytest.approx(sig.weight)


def test_score_all_buckets_uses_canonical_facade():
    """Analyze bucket-fit must score via the Scan Stage B facade, not raw screener.score."""
    from services import analyze_service

    fake_outcome = MagicMock()
    fake_outcome.score = 61.5
    fake_outcome.signals = []
    fake_outcome.risk = MagicMock(value="high")
    fake_outcome.metrics = {}

    fake_ctx = _ctx("FAC")
    screener = MagicMock()
    screener.enrich.return_value = fake_ctx
    screener.hard_filter.return_value = True
    screener.ps = MagicMock()

    with (
        patch.object(
            analyze_service,
            "_SCREENERS",
            {Bucket.penny: lambda: screener, Bucket.compounder: lambda: screener},
        ),
        patch(
            "services.scoring_facade.score_symbol_canonical",
            return_value=fake_outcome,
        ) as canonical,
        patch("services.analyze_service.PriceService"),
    ):
        out = analyze_service.score_all_buckets("FAC")

    assert canonical.call_count == 2
    assert out["scores"]["penny"]["score"] == 61.5
    screener.score.assert_not_called()
