"""Factor Discovery statistics helpers tests."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engines.factor.discovery.statistics import (
    benjamini_hochberg,
    bonferroni_correction,
    confidence_interval,
    t_statistic,
)


def test_bonferroni_stricter_than_raw():
    pvals = [0.04]
    assert bonferroni_correction(pvals, 10, 0.05) == [False]


def test_bh_can_pass_some():
    pvals = [0.001, 0.02, 0.03, 0.5]
    passed = benjamini_hochberg(pvals, 0.05)
    assert passed[0] is True


def test_t_stat_positive_mean():
    vals = [0.1, 0.2, 0.15, 0.12]
    t = t_statistic(vals)
    assert t is not None and t > 0


def test_confidence_interval_contains_mean():
    vals = [0.1, 0.2, 0.15, 0.12, 0.18]
    ci = confidence_interval(vals)
    assert ci is not None
    assert ci[0] < sum(vals) / len(vals) < ci[1]
