"""Concurrency behavior tests (SQLite-safe via uniqueness constraints)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engines.factor.discovery.parser import parse_factor_expression
from engines.factor.discovery.formatter import format_factor_expression
from models.schemas_factor_discovery import FactorDefinition, FactorDirection
from services.factor_discovery.errors import FactorDefinitionConflictError
from services.factor_discovery.repositories import FactorDefinitionRepository, FactorSealedReceiptRepository
from services.factor_discovery.errors import FactorDiscoveryError


def test_factor_version_race_same_content_idempotent(isolated_backend_env):
    ast = parse_factor_expression("rank(return_126d)")
    definition = FactorDefinition(
        factor_id="race_factor",
        version="1.0.0",
        display_name="Race",
        expression=ast,
        expected_direction=FactorDirection.HIGHER_IS_BETTER,
        intended_universe="research",
        rebalance_frequency="monthly",
        holding_period_sessions=21,
    )
    repo = FactorDefinitionRepository()
    dsl = format_factor_expression(ast)
    repo.create_version(definition, created_by="a", canonical_dsl=dsl, canonical_ast=definition.expression.model_dump(mode="json"))
    repo.create_version(definition, created_by="b", canonical_dsl=dsl, canonical_ast=definition.expression.model_dump(mode="json"))
    row = repo.get("race_factor", "1.0.0")
    assert row.formula_hash == definition.formula_hash()


def test_sealed_reservation_duplicate_conflict(isolated_backend_env):
    repo = FactorSealedReceiptRepository()
    fields = {
        "run_id": "run1",
        "factor_id": "f1",
        "factor_version": "1.0.0",
        "formula_hash": "fh1",
        "plan_hash": "ph1",
        "panel_snapshot_id": "snap1",
        "period_hash": "per1",
        "validation_config_hash": "vc1",
        "access_policy_version": "v1",
        "closed_artifact_hash": "ca1",
        "sealed_data_commitment_hash": "sd1",
        "approval_reference": "apr1",
        "requested_by": "user",
        "reason": "test",
    }
    repo.reserve(**fields)
    with pytest.raises(FactorDiscoveryError) as exc:
        repo.reserve(**fields)
    assert exc.value.code == "SEALED_TEST_ALREADY_RESERVED"
