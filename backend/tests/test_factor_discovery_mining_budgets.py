"""Budget enforcement tests for mining sessions."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.factor_discovery.mining.budget_service import check_budget, load_usage, reserve_usage
from services.factor_discovery.mining.errors import MiningBudgetExceededError
from services.factor_discovery.mining.models import FactorMiningBudgetPolicy, SessionUsageCounters


def test_hypothesis_budget_exceeded():
    policy = FactorMiningBudgetPolicy(max_hypotheses=1)
    usage = SessionUsageCounters(hypotheses_generated=1)
    with pytest.raises(MiningBudgetExceededError):
        check_budget(policy, usage, operation="hypothesis")


def test_reserve_usage_increments():
    usage = load_usage(None)
    updated = reserve_usage(usage, "llm")
    assert updated.llm_interactions == 1
