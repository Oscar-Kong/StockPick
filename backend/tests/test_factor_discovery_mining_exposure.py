"""Validation exposure budget tests."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.factor_discovery.mining.errors import MiningValidationExposureExceededError
from services.factor_discovery.mining.exposure_service import MiningExposureService
from services.factor_discovery.mining.models import ContextTier, FactorMiningBudgetPolicy


def test_discovery_only_skips_exposure_check():
    svc = MiningExposureService()
    svc.check_exposure(
        session_id="s1",
        lineage_id="l1",
        formula_hash="h1",
        budget=FactorMiningBudgetPolicy(max_validation_exposures_per_lineage=0),
        context_tier=ContextTier.DISCOVERY_ONLY,
    )


def test_lineage_exposure_limit(monkeypatch):
    from services.factor_discovery.mining.repositories import FactorMiningExposureRepository

    monkeypatch.setattr(FactorMiningExposureRepository, "count_for_lineage", lambda self, s, l: 2)
    monkeypatch.setattr(FactorMiningExposureRepository, "count_for_formula", lambda self, s, f: 0)
    svc = MiningExposureService()
    with pytest.raises(MiningValidationExposureExceededError):
        svc.check_exposure(
            session_id="s1",
            lineage_id="l1",
            formula_hash="h1",
            budget=FactorMiningBudgetPolicy(max_validation_exposures_per_lineage=2),
            context_tier=ContextTier.DISCOVERY_PLUS_VALIDATION_SUMMARY,
        )
