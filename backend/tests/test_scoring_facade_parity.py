"""Scoring facade parity — Scan and Watchlist must agree on the same input.

The whole point of `services.scoring_facade.score_symbol_canonical` is to
delete the historical drift between:
  - `services.scan_scoring.score_stage_b_candidate` (used by Scan Stage B)
  - the bespoke pipeline that `services.watchlist_scanner.analyze_symbol`
    used to run by hand

These tests pin the canonical-score contract: same CandidateContext + same
screener → byte-identical numeric `score`, `risk`, and `signals` from both
entry points. If `USE_SCORING_ENGINE_IN_SCAN` flips, both move together.
"""
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

from models.schemas import Bucket, RiskLevel
from screeners.base import CandidateContext, WeightedSignal
from services.scan_scoring import score_stage_b_candidate
from services.scoring_facade import score_symbol_canonical


def _ctx(symbol: str = "AAA") -> CandidateContext:
    dates = pd.date_range("2025-01-01", periods=40, freq="B")
    closes = [10.0 + i * 0.1 for i in range(40)]
    hist = pd.DataFrame(
        {
            "date": dates,
            "open": closes,
            "high": [c + 0.2 for c in closes],
            "low": [c - 0.2 for c in closes],
            "close": closes,
            "volume": [1_500_000] * 40,
        }
    )
    return CandidateContext(
        symbol=symbol.upper(),
        price=float(closes[-1]),
        info={"sector": "Technology", "marketCap": 5_000_000_000},
        fundamentals={},
        history=hist,
    )


def _screener_returning(score: float) -> MagicMock:
    s = MagicMock()
    s.score.return_value = (
        score,
        [WeightedSignal("Mock", score, 1.0, "mock")],
        RiskLevel.medium,
        "Mock summary",
        {"raw_score": score},
    )
    return s


@pytest.fixture(autouse=True)
def _stub_external_pipeline():
    """Pin the parts of the pipeline that hit the network or DB so this test
    measures the facade itself, not what enrich_metrics happens to return."""
    with patch(
        "services.scan_scoring.enrich_metrics",
        side_effect=lambda sym, info, fund, m, bucket, **kw: {**m, "enriched": True},
    ), patch(
        "services.scan_scoring._apply_openbb_adjustment", side_effect=lambda score, metrics: score
    ), patch("services.scan_scoring.PERSIST_SCORE_ATTRIBUTION", False):
        yield


def test_facade_score_matches_scan_stage_b_with_engine_off():
    """When USE_SCORING_ENGINE_IN_SCAN is false (the production default),
    the canonical facade must return the same numeric score, risk, and
    signal list as `score_stage_b_candidate` for the same inputs."""
    with patch("services.scan_scoring.resolve_scan_scoring_mode", return_value="legacy"):
        ctx_a = _ctx("AAA")
        scan_screener = _screener_returning(72.0)
        scan_outcome = score_stage_b_candidate(
            ctx=ctx_a,
            screener=scan_screener,
            bucket=Bucket.medium,
            symbol="AAA",
            quality_score=80.0,
            strategy_version="vTest",
            quality_filter={},
        )

        # Fresh ctx/screener (mocks are stateful) but identical inputs.
        ctx_b = _ctx("AAA")
        facade_screener = _screener_returning(72.0)
        facade_outcome = score_symbol_canonical(
            ctx=ctx_b,
            screener=facade_screener,
            bucket=Bucket.medium,
            symbol="AAA",
            quality_score=80.0,
            strategy_version="vTest",
        )

    assert facade_outcome.score == scan_outcome.score
    assert facade_outcome.risk == scan_outcome.risk
    assert facade_outcome.scoring_engine_used == scan_outcome.scoring_engine_used is False
    # Signals carry their own __eq__ via dataclass; compare by (name, value).
    assert [(s.name, s.value) for s in facade_outcome.signals] == [
        (s.name, s.value) for s in scan_outcome.signals
    ]


def test_facade_defaults_quality_filter_to_empty_dict():
    """Callers that omit `quality_filter` (Watchlist, Analyze) must still get
    a metrics dict with `quality_filter` present so downstream readers do
    not crash on KeyError."""
    with patch("services.scan_scoring.resolve_scan_scoring_mode", return_value="legacy"):
        outcome = score_symbol_canonical(
            ctx=_ctx("BBB"),
            screener=_screener_returning(60.0),
            bucket=Bucket.medium,
            symbol="BBB",
            quality_score=70.0,
            strategy_version="vTest",
        )
    assert outcome.metrics.get("quality_filter") == {}


def test_facade_falls_back_to_default_strategy_version_when_omitted():
    """The facade is allowed to look up the active strategy version itself —
    callers that do not have a StrategyRegistry handy should not have to
    construct one. We stub the registry to return a known value."""
    fake = MagicMock()
    fake.get_active.return_value = MagicMock(version_id="vAuto")
    with patch("data.strategy_registry.StrategyRegistry", return_value=fake), patch(
        "services.scan_scoring.resolve_scan_scoring_mode", return_value="legacy"
    ):
        outcome = score_symbol_canonical(
            ctx=_ctx("CCC"),
            screener=_screener_returning(55.0),
            bucket=Bucket.penny,
            symbol="CCC",
            quality_score=None,
        )
    assert outcome.metrics["strategy_version"] == "vAuto"


def test_facade_propagates_engine_flag_when_enabled():
    """When the flag flips, the facade must also flip — same as Scan does.
    We stub ScoringEngine.score so we do not depend on the real engine."""
    from types import SimpleNamespace

    fake_factors = [
        SimpleNamespace(
            factor_id="f1",
            display_name="Fake",
            norm_score=70.0,
            weight=1.0,
            contribution=70.0,
            description="fake",
        )
    ]
    fake_scoring = SimpleNamespace(
        sleeve="medium",
        signals=[WeightedSignal("Engine", 70.0, 1.0, "engine")],
        factors=fake_factors,
        raw_score=70.0,
        score_after_regime=70.0,
        regime_mult=1.0,
        sector_tilt=0.0,
        dq_multiplier=1.0,
        score_after_dq=70.0,
        openbb_delta=0.0,
        score_after_openbb=70.0,
        final_score=70.0,
        risk_level=RiskLevel.medium,
        summary="engine",
        metrics={},
    )
    with patch("services.scan_scoring.resolve_scan_scoring_mode", return_value="engine"), patch(
        "services.scan_scoring.ScoringEngine.score", return_value=fake_scoring
    ):
        outcome = score_symbol_canonical(
            ctx=_ctx("DDD"),
            screener=_screener_returning(50.0),
            bucket=Bucket.medium,
            symbol="DDD",
            quality_score=80.0,
            strategy_version="vTest",
        )
    assert outcome.scoring_engine_used is True
    assert outcome.score == 70.0
