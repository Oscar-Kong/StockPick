"""Tests for Stage A preliminary ranking."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from models.schemas import Bucket
from services.stage_a_ranking import (
    COMPOUNDER_FEATURE_WEIGHTS,
    PENNY_FEATURE_WEIGHTS,
    StageACandidate,
    rank_stage_a_candidates,
    select_stage_b_symbols,
)


def _history(
    *,
    base: float = 2.0,
    bars: int = 60,
    daily_step: float = 0.0,
    volume: float = 1_500_000.0,
    volume_tail_mult: float = 1.0,
) -> pd.DataFrame:
    dates = pd.date_range("2025-01-01", periods=bars, freq="B")
    closes = [base + i * daily_step for i in range(bars)]
    volumes = [volume] * bars
    if volume_tail_mult != 1.0 and bars >= 5:
        for i in range(-5, 0):
            volumes[i] = volume * volume_tail_mult
    return pd.DataFrame(
        {
            "date": dates,
            "open": closes,
            "high": [c + 0.05 for c in closes],
            "low": [c - 0.05 for c in closes],
            "close": closes,
            "volume": volumes,
        }
    )


def test_later_alphabet_symbol_ranks_above_weak_early_symbol():
    """Alphabetically later strong features must beat alphabetically earlier weak names."""
    bulk_hist = {
        "AAA": _history(base=2.0, daily_step=0.0, volume_tail_mult=1.0),
        "ZZZ": _history(base=2.0, daily_step=0.08, volume_tail_mult=3.0),
    }
    result = rank_stage_a_candidates(
        Bucket.penny,
        bulk_hist,
        universe=["AAA", "ZZZ"],
        apply_eligibility=False,
    )
    assert [c.symbol for c in result.ranked] == ["ZZZ", "AAA"]
    assert result.ranked[0].pre_score > result.ranked[1].pre_score


def test_stage_b_receives_descending_pre_score_order():
    bulk_hist = {
        "C": _history(daily_step=0.02),
        "A": _history(daily_step=0.10),
        "B": _history(daily_step=0.05),
    }
    result = rank_stage_a_candidates(
        Bucket.penny,
        bulk_hist,
        universe=["A", "B", "C"],
        apply_eligibility=False,
    )
    symbols = select_stage_b_symbols(result.ranked, 3)
    assert symbols == ["A", "B", "C"]
    scores = [c.pre_score for c in result.ranked]
    assert scores == sorted(scores, reverse=True)


def test_equal_scores_use_symbol_tie_break():
    candidates = [
        StageACandidate(symbol="ZZZ", pre_score=50.0, features={}),
        StageACandidate(symbol="AAA", pre_score=50.0, features={}),
        StageACandidate(symbol="MMM", pre_score=50.0, features={}),
    ]
    candidates.sort(key=lambda c: (-c.pre_score, c.symbol))
    assert [c.symbol for c in candidates] == ["AAA", "MMM", "ZZZ"]
    assert select_stage_b_symbols(candidates, 2) == ["AAA", "MMM"]


def test_missing_optional_features_do_not_eliminate_candidate():
    """Compounder without cached fundamental quality should still rank."""
    bulk_hist = {"CMP1": _history(base=50.0, bars=120, daily_step=0.05, volume=2_000_000.0)}
    result = rank_stage_a_candidates(
        Bucket.compounder,
        bulk_hist,
        universe=["CMP1"],
        cached_quality={},
        apply_eligibility=False,
    )
    assert len(result.ranked) == 1
    assert "fundamental_quality_missing" in result.ranked[0].warnings
    assert "fundamental_quality" not in result.ranked[0].features
    assert result.ranked[0].pre_score > 0


def test_penny_and_compounder_use_different_weight_profiles():
    hist = _history(bars=120, daily_step=0.03, volume=2_000_000.0, volume_tail_mult=2.0)
    bulk_hist = {"SYM": hist}
    penny = rank_stage_a_candidates(
        Bucket.penny,
        bulk_hist,
        universe=["SYM"],
        apply_eligibility=False,
    ).ranked[0]
    compounder = rank_stage_a_candidates(
        Bucket.compounder,
        bulk_hist,
        universe=["SYM"],
        cached_quality={"SYM": 80.0},
        apply_eligibility=False,
    ).ranked[0]

    assert set(penny.features) <= set(PENNY_FEATURE_WEIGHTS)
    assert set(compounder.features) <= set(COMPOUNDER_FEATURE_WEIGHTS)
    assert "rel_volume" in penny.features
    assert "trend_12m" in compounder.features
    assert penny.pre_score != compounder.pre_score or penny.features != compounder.features


def test_excluded_symbols_include_rejection_reason():
    bulk_hist = {"LOW": _history(base=0.10)}  # below penny min price by default config
    result = rank_stage_a_candidates(Bucket.penny, bulk_hist, universe=["LOW"])
    assert not result.ranked
    assert result.excluded[0].symbol == "LOW"
    assert result.excluded[0].rejection_reason == "price_out_of_range"


def test_stage_a_candidate_exposes_rank_features_and_warnings():
    bulk_hist = {"AAA": _history(daily_step=0.04)}
    result = rank_stage_a_candidates(
        Bucket.penny,
        bulk_hist,
        universe=["AAA"],
        apply_eligibility=False,
    )
    candidate: StageACandidate = result.ranked[0]
    payload = candidate.to_dict()
    assert payload["rank"] == 1
    assert payload["pre_score"] >= 0
    assert payload["features"]
    assert isinstance(payload["warnings"], list)


def test_example_five_candidate_ranking_snapshot():
    """Document-style snapshot for five synthetic penny candidates."""
    specs = {
        "ALPHA": dict(daily_step=0.0, volume_tail_mult=1.0),
        "BETA": dict(daily_step=0.02, volume_tail_mult=1.2),
        "GAMMA": dict(daily_step=0.04, volume_tail_mult=1.8),
        "DELTA": dict(daily_step=0.06, volume_tail_mult=2.5),
        "EPSILON": dict(daily_step=0.08, volume_tail_mult=3.0),
    }
    bulk_hist = {sym: _history(**kw) for sym, kw in specs.items()}
    result = rank_stage_a_candidates(
        Bucket.penny,
        bulk_hist,
        universe=list(specs),
        apply_eligibility=False,
    )
    ordered = [c.symbol for c in result.ranked]
    assert ordered[0] == "EPSILON"
    assert ordered[-1] == "ALPHA"
    assert select_stage_b_symbols(result.ranked, 3) == ordered[:3]
