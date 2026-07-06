"""Factor Discovery validation hashing tests."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engines.factor.discovery.validation_hashing import validation_artifact_hash, validation_config_hash
from engines.factor.discovery.validation_models import FactorValidationConfig, SealedTestAccess


def test_config_hash_changes_with_primary_horizon():
    a = FactorValidationConfig(primary_horizon_sessions=5)
    b = FactorValidationConfig(primary_horizon_sessions=21)
    assert validation_config_hash(a) != validation_config_hash(b)


def test_artifact_hash_changes_when_sealed_opened():
    base = dict(
        formula_hash="sha256:abc",
        plan_hash="sha256:def",
        execution_hash="sha256:ghi",
        outcome_hashes={"21": "sha256:jkl"},
        period_resolution_hash="sha256:mno",
        validation_config_hash_value="sha256:pqr",
    )
    closed = validation_artifact_hash(**base, sealed_opened=False)
    access = SealedTestAccess(
        reason="t",
        requested_by="u",
        approval_reference="A1",
        expected_formula_hash="sha256:abc",
        expected_plan_hash="sha256:def",
    )
    opened = validation_artifact_hash(**base, sealed_opened=True, sealed_access=access)
    assert closed != opened
