"""Revision diff policy tests."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engines.factor.discovery.parser import parse_factor_expression
from services.factor_discovery.mining.errors import MiningRevisionPolicyError
from services.factor_discovery.mining.models import FactorMiningBudgetPolicy
from services.factor_discovery.mining.revision_diff import diff_revision, validate_revision_policy


def test_valid_minor_revision():
    parent = parse_factor_expression("rank(return_126d)")
    child = parse_factor_expression("rank(return_63d)")
    diff = diff_revision(parent, child)
    validate_revision_policy(diff, budget=FactorMiningBudgetPolicy(), evaluated_hashes=set())


def test_revision_cycle_rejected():
    parent = parse_factor_expression("rank(return_126d)")
    child = parse_factor_expression("rank(return_63d)")
    diff = diff_revision(parent, child)
    with pytest.raises(MiningRevisionPolicyError):
        validate_revision_policy(diff, budget=FactorMiningBudgetPolicy(), evaluated_hashes={diff.child_formula_hash})
