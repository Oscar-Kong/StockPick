"""Tests for decomposed scan scores and final ranking diversification."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from models.schemas import Bucket, RiskLevel, StockResult
from services.scan_decomposition import build_decomposed_scores, compute_ranking_score
from services.scan_final_ranking import (
    EXCLUDED_BY_CORRELATION_LIMIT,
    EXCLUDED_BY_SECTOR_LIMIT,
    RETAINED_BY_PERSISTENCE,
    apply_final_scan_ranking,
    apply_persistence,
    to_ranked_candidates,
)
from services.scan_issuer import issuer_key
from screeners.base import WeightedSignal


def _history(*, base: float = 2.0, volume: float = 2_000_000, bars: int = 80) -> pd.DataFrame:
    dates = pd.date_range("2025-01-01", periods=bars, freq="B")
    closes = [base + i * 0.01 for i in range(bars)]
    return pd.DataFrame(
        {
            "date": dates,
            "open": closes,
            "high": [c + 0.05 for c in closes],
            "low": [c - 0.05 for c in closes],
            "close": closes,
            "volume": [volume] * bars,
        }
    )


def _stock(
    symbol: str,
    *,
    ranking: float,
    alpha: float | None = None,
    confidence: float | None = None,
    tradability: float | None = None,
    sector: str = "Technology",
    metrics: dict | None = None,
) -> StockResult:
    m = dict(metrics or {})
    m.setdefault("sector", sector)
    m["ranking_score"] = ranking
    m["alpha_score"] = alpha if alpha is not None else ranking
    m["confidence_score"] = confidence if confidence is not None else 70.0
    m["tradability_score"] = tradability if tradability is not None else 70.0
    m.setdefault("_issuer_key", issuer_key(symbol, {"sector": m.get("sector", sector)}))
    return StockResult(
        symbol=symbol,
        price=2.5,
        score=ranking,
        alpha_score=m["alpha_score"],
        confidence_score=m["confidence_score"],
        tradability_score=m["tradability_score"],
        ranking_score=ranking,
        signals=[],
        risk_level=RiskLevel.medium,
        summary="test",
        bucket=Bucket.penny,
        metrics=m,
    )


def test_high_alpha_low_confidence_ranking_below_alpha():
    signals = [WeightedSignal("Momentum", 90.0, 1.0, "")]
    metrics = {"raw_score": 88.0, "data_quality_score": 30.0, "provider_limited_partial_data": True}
    dec = build_decomposed_scores(
        raw_score=88.0,
        signals=signals,
        metrics=metrics,
        bucket=Bucket.penny,
        price=2.0,
        history=_history(),
        quality_score=30.0,
        hist_len=80,
    )
    assert dec.alpha_score >= 85.0
    assert dec.confidence_score < 55.0
    assert dec.ranking_score < dec.alpha_score


def test_high_alpha_low_tradability():
    signals = [WeightedSignal("Vol spike", 85.0, 1.0, "")]
    metrics = {
        "raw_score": 84.0,
        "average_dollar_volume_20d": 200_000,
        "atr_percent": 18.0,
        "spread_estimate_pct": 12.0,
    }
    dec = build_decomposed_scores(
        raw_score=84.0,
        signals=signals,
        metrics=metrics,
        bucket=Bucket.penny,
        price=2.0,
        history=_history(volume=100_000),
        quality_score=75.0,
        hist_len=80,
    )
    assert dec.alpha_score >= 80.0
    assert dec.tradability_score < 50.0
    assert dec.ranking_score < dec.alpha_score


def test_ranking_formula_bucket_weights():
    score, weights = compute_ranking_score(80.0, 60.0, 70.0, bucket=Bucket.penny)
    expected = 80 * weights["alpha"] + 60 * weights["confidence"] + 70 * weights["tradability"]
    assert score == pytest.approx(round(expected, 1), abs=0.2)


def test_sector_concentration_limit():
    results = [
        _stock("A1", ranking=90, sector="Technology"),
        _stock("A2", ranking=88, sector="Technology"),
        _stock("A3", ranking=86, sector="Technology"),
        _stock("A4", ranking=84, sector="Technology"),
        _stock("B1", ranking=70, sector="Healthcare"),
    ]
    out = apply_final_scan_ranking(results, bucket=Bucket.penny, max_results=4)
    sectors = [(r.metrics or {}).get("sector") for r in out.results]
    assert sectors.count("Technology") <= 3
    reasons = {e.reason for e in out.exclusions}
    assert EXCLUDED_BY_SECTOR_LIMIT in reasons


def test_share_class_deduplication():
    results = [
        _stock("GOOGL", ranking=88, sector="Technology", metrics={"_issuer_key": "ALPHABET"}),
        _stock("GOOG", ranking=86, sector="Technology", metrics={"_issuer_key": "ALPHABET"}),
        _stock("MSFT", ranking=80, sector="Technology", metrics={"_issuer_key": "MICROSOFT"}),
    ]
    out = apply_final_scan_ranking(results, bucket=Bucket.penny, max_results=3)
    syms = {r.symbol for r in out.results}
    assert "GOOGL" in syms or "GOOG" in syms
    assert "MSFT" in syms
    assert not ("GOOGL" in syms and "GOOG" in syms)


def test_correlation_cluster_limit():
    bars = 60
    base = np.linspace(10, 12, bars)
    noise = np.random.default_rng(42).normal(0, 0.01, bars)
    close_a = base + noise
    close_b = base + noise * 0.95 + 0.002
    close_c = base + noise * 0.98 + 0.001
    bulk = {
        "COR1": pd.DataFrame({"close": close_a, "volume": [1e6] * bars}),
        "COR2": pd.DataFrame({"close": close_b, "volume": [1e6] * bars}),
        "COR3": pd.DataFrame({"close": close_c, "volume": [1e6] * bars}),
    }
    results = [
        _stock("COR1", ranking=90, sector="Tech"),
        _stock("COR2", ranking=88, sector="Tech"),
        _stock("COR3", ranking=86, sector="Energy"),
    ]
    out = apply_final_scan_ranking(results, bucket=Bucket.penny, max_results=3, bulk_hist=bulk)
    cor_in_final = [r.symbol for r in out.results if r.symbol.startswith("COR")]
    assert len(cor_in_final) <= 2
    reasons = {e.reason for e in out.exclusions}
    assert EXCLUDED_BY_CORRELATION_LIMIT in reasons


def test_persistence_threshold():
    ranked = to_ranked_candidates(
        [
            _stock("NEW", ranking=72.0, confidence=80),
            _stock("OLD", ranking=70.5, confidence=75),
        ],
        None,
    )
    selected = [c for c in ranked if c.symbol == "NEW"]
    prev = [{"symbol": "OLD", "score": 70.0, "metrics": {"ranking_score": 70.0}}]
    after, _, retained = apply_persistence(
        selected,
        ranked,
        bucket=Bucket.penny,
        max_results=1,
        previous_results=prev,
        delta=3.0,
    )
    assert [c.symbol for c in after] == ["NEW"]
    assert retained == []

    ranked2 = to_ranked_candidates(
        [
            _stock("NEW", ranking=72.0),
            _stock("OLD", ranking=76.0),
        ],
        None,
    )
    selected2 = [c for c in ranked2 if c.symbol == "NEW"]
    after2, _, retained2 = apply_persistence(
        selected2,
        ranked2,
        bucket=Bucket.penny,
        max_results=1,
        previous_results=prev,
        delta=3.0,
    )
    assert retained2 == ["OLD"]
    assert any(c.symbol == "OLD" for c in after2)
    assert (after2[0].result.metrics or {}).get("ranking_note") == RETAINED_BY_PERSISTENCE

    ranked3 = to_ranked_candidates(
        [
            _stock("NEW", ranking=72.0),
            _stock("OLD", ranking=74.0),
        ],
        None,
    )
    selected3 = [c for c in ranked3 if c.symbol == "NEW"]
    after3, _, retained3 = apply_persistence(
        selected3,
        ranked3,
        bucket=Bucket.penny,
        max_results=1,
        previous_results=prev,
        delta=3.0,
    )
    assert [c.symbol for c in after3] == ["NEW"]
    assert retained3 == []


def test_deterministic_output():
    results = [
        _stock("Z", ranking=70, sector="Healthcare"),
        _stock("A", ranking=70, sector="Energy"),
        _stock("M", ranking=70, sector="Technology"),
    ]
    out1 = apply_final_scan_ranking(results, bucket=Bucket.penny, max_results=3)
    out2 = apply_final_scan_ranking(results, bucket=Bucket.penny, max_results=3)
    assert [r.symbol for r in out1.results] == [r.symbol for r in out2.results]


def test_insufficient_candidates_after_diversification():
    """When every name shares a cluster, return fewer than max_results rather than relax correlation."""
    bars = 40
    base = np.linspace(5, 6, bars)
    noise = np.random.default_rng(7).normal(0, 0.005, bars)
    bulk = {
        f"C{i}": pd.DataFrame({"close": base + noise * (1 + i * 0.01), "volume": [1e6] * bars})
        for i in range(1, 5)
    }
    results = [_stock(f"C{i}", ranking=90 - i, sector="Tech") for i in range(1, 5)]
    out = apply_final_scan_ranking(results, bucket=Bucket.penny, max_results=4, bulk_hist=bulk)
    assert len(out.results) == 2
    assert len(out.results) < 4
