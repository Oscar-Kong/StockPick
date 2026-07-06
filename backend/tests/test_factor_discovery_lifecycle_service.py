"""Factor lifecycle service tests."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from models.schemas_factor_discovery import FactorLifecycleStatus
from services.factor_discovery.errors import FactorLifecycleError, ProductionPromotionError
from services.factor_discovery.lifecycle_service import FactorLifecycleService, LifecycleTransitionRequest
from tests.fixtures.factor_discovery.persistence_helpers import seed_family_and_definition


def test_draft_to_compiled_requires_formula_hash(isolated_backend_env):
    family_id, definition, _ = seed_family_and_definition(status=FactorLifecycleStatus.DRAFT)
    svc = FactorLifecycleService()
    row = __import__(
        "services.factor_discovery.repositories", fromlist=["FactorDefinitionRepository"]
    ).FactorDefinitionRepository().get(definition.factor_id, definition.version)
    with pytest.raises(FactorLifecycleError):
        svc.transition(
            LifecycleTransitionRequest(
                factor_id=definition.factor_id,
                factor_version=definition.version,
                target_status=FactorLifecycleStatus.COMPILED,
                actor_type="system",
                actor_identifier="compiler",
                reason="compiled ok",
                expected_formula_hash="wrong",
            )
        )
    event_id = svc.transition(
        LifecycleTransitionRequest(
            factor_id=definition.factor_id,
            factor_version=definition.version,
            target_status=FactorLifecycleStatus.COMPILED,
            actor_type="system",
            actor_identifier="compiler",
            reason="compiled ok",
            expected_formula_hash=row.formula_hash,
        )
    )
    assert event_id.startswith("fdevt_")


def test_production_promotion_not_available(isolated_backend_env):
    _, definition, _ = seed_family_and_definition()
    svc = FactorLifecycleService()
    with pytest.raises(ProductionPromotionError) as exc:
        svc.transition(
            LifecycleTransitionRequest(
                factor_id=definition.factor_id,
                factor_version=definition.version,
                target_status=FactorLifecycleStatus.PRODUCTION,
                actor_type="human",
                actor_identifier="user",
                reason="promote",
            )
        )
    assert exc.value.code == "PRODUCTION_PROMOTION_NOT_AVAILABLE"
