"""Model contract tests for mining sessions."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.factor_discovery.mining.models import (
    FactorMiningAutoPolicy,
    FactorMiningBudgetPolicy,
    FactorRevisionProposal,
    MiningSessionMode,
    MINING_POLICY_VERSION,
)


def test_policy_schema_version():
    assert FactorMiningBudgetPolicy().schema_version == MINING_POLICY_VERSION


def test_auto_policy_defaults_disabled():
    auto = FactorMiningAutoPolicy()
    assert auto.auto_launch_experiments is False
    assert auto.auto_approve_revisions is False


def test_revision_proposal_rejects_extra_fields():
    with pytest.raises(Exception):
        FactorRevisionProposal(
            parent_formula_candidate_id="c1",
            parent_formula_hash="h1",
            lineage_id="l1",
            revision_round=1,
            revision_rationale="simplify",
            proposed_dsl="rank(return_126d)",
            open_sealed_test=True,
        )


def test_mining_modes():
    assert MiningSessionMode.SUPERVISED.value == "supervised"
