"""Security tests for mining loop."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config
from engines.quant_db import init_quant_db
from services.factor_discovery.mining.errors import MiningFeatureDisabledError
from services.factor_discovery.mining.orchestrator import FactorMiningOrchestrator
from services.factor_discovery.mining.policies import require_mining_enabled


def test_mining_disabled_by_default():
    with pytest.raises(MiningFeatureDisabledError):
        require_mining_enabled()


def test_orchestrator_does_not_import_sealed():
    text = open(
        Path(__file__).resolve().parents[1] / "services/factor_discovery/mining/orchestrator.py",
        encoding="utf-8",
    ).read()
    assert "open_sealed" not in text.lower()
    assert "SealedTestService" not in text
