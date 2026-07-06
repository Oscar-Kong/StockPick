"""Factor Discovery sealed-test access tests."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engines.factor.discovery.sealed_test import validate_sealed_test_access
from engines.factor.discovery.validation_errors import HashMismatchError, SealedTestAccessError
from engines.factor.discovery.validation_models import SealedTestAccess


def test_formula_hash_mismatch_rejected():
    access = SealedTestAccess(
        reason="t",
        requested_by="u",
        approval_reference="A1",
        expected_formula_hash="sha256:wrong",
        expected_plan_hash="sha256:plan",
    )
    with pytest.raises(HashMismatchError):
        validate_sealed_test_access(access, formula_hash="sha256:right", plan_hash="sha256:plan")


def test_missing_approval_rejected():
    access = SealedTestAccess(
        reason="t",
        requested_by="u",
        approval_reference="",
        expected_formula_hash="sha256:f",
        expected_plan_hash="sha256:p",
    )
    with pytest.raises(SealedTestAccessError):
        validate_sealed_test_access(access, formula_hash="sha256:f", plan_hash="sha256:p")
