"""Sealed receipt reservation and failure policy tests."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.factor_discovery.errors import FactorDiscoveryError
from services.factor_discovery.repositories import FactorSealedReceiptRepository


def test_failed_receipt_blocks_ordinary_retry(isolated_backend_env):
    repo = FactorSealedReceiptRepository()
    fields = {
        "run_id": "run_sealed",
        "factor_id": "sf1",
        "factor_version": "1.0.0",
        "formula_hash": "fh",
        "plan_hash": "ph",
        "panel_snapshot_id": "snap",
        "period_hash": "per",
        "validation_config_hash": "vc",
        "access_policy_version": "v1",
        "closed_artifact_hash": "ca",
        "sealed_data_commitment_hash": "sd",
        "approval_reference": "apr",
        "requested_by": "user",
        "reason": "open",
    }
    rid = repo.reserve(**fields)
    repo.fail(rid, failure_code="SEALED_COMPUTATION_FAILED")
    row = repo.get(rid)
    assert row.status == "FAILED"
    with pytest.raises(FactorDiscoveryError) as exc:
        repo.reserve(**fields)
    assert exc.value.code == "SEALED_RECEIPT_FAILED"
