"""Attempt ledger and multiple-testing family counting tests."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engines.factor_discovery_models import FactorDiscoveryAttempt
from services.factor_discovery.multiple_testing_service import derive_family_size


def _att(**kw) -> FactorDiscoveryAttempt:
    defaults = {
        "attempt_id": "a1",
        "run_id": "r1",
        "research_family_id": "f1",
        "factor_id": "fac",
        "factor_version": "1.0.0",
        "attempt_kind": "NEW_FORMULA",
        "attempt_sequence": 1,
        "stage_reached": "complete",
        "outcome": "validation_completed",
        "primary_horizon_sessions": 21,
        "validation_config_hash": "h1",
        "formula_hash": "fh1",
        "metric_evaluation_started": True,
    }
    defaults.update(kw)
    return FactorDiscoveryAttempt(**defaults)


def test_parse_failure_excluded_from_family_size():
    attempts = [
        _att(outcome="parse_failed", formula_hash="fh_parse", metric_evaluation_started=False),
        _att(outcome="validation_completed", formula_hash="fh_ok"),
    ]
    size = derive_family_size(attempts, primary_horizon_sessions=21, validation_config_family_id="default_v1")
    assert size.derived_family_size == 1
    assert "fh_ok" in size.evaluated_formula_hashes


def test_same_formula_technical_retry_deduplicated():
    attempts = [
        _att(outcome="validation_completed", formula_hash="fh_a", attempt_sequence=1),
        _att(outcome="validation_completed", formula_hash="fh_a", attempt_sequence=2),
    ]
    size = derive_family_size(attempts, primary_horizon_sessions=21, validation_config_family_id="default_v1")
    assert size.derived_family_size == 1


def test_new_formula_increments_family_size():
    attempts = [
        _att(outcome="validation_completed", formula_hash="fh_a"),
        _att(outcome="validation_completed", formula_hash="fh_b"),
    ]
    size = derive_family_size(attempts, primary_horizon_sessions=21, validation_config_family_id="default_v1")
    assert size.derived_family_size == 2


def test_different_horizon_separated():
    attempts = [
        _att(outcome="validation_completed", formula_hash="fh_a", primary_horizon_sessions=21),
        _att(outcome="validation_completed", formula_hash="fh_b", primary_horizon_sessions=63),
    ]
    size = derive_family_size(attempts, primary_horizon_sessions=21, validation_config_family_id="default_v1")
    assert size.derived_family_size == 1
