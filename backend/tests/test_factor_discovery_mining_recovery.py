"""Crash recovery tests for mining sessions."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engines.quant_db import init_quant_db
from services.factor_discovery.mining.errors import MiningRecoveryError
from services.factor_discovery.mining.recovery_service import MiningRecoveryService
from services.factor_discovery.mining.session_service import FactorMiningSessionService
from tests.fixtures.factor_discovery.mining.helpers import authorize_and_start, enable_mining, mining_session_request


def test_recovery_missing_session():
    init_quant_db()
    with pytest.raises(MiningRecoveryError):
        MiningRecoveryService().recover_session("missing")


def test_recovery_after_authorization(isolated_backend_env, monkeypatch):
    init_quant_db()
    enable_mining(monkeypatch)
    session_svc = FactorMiningSessionService()
    created = session_svc.create_session(mining_session_request())
    authorize_and_start(session_svc, created["session_id"])
    out = MiningRecoveryService().recover_session(created["session_id"])
    assert out["recoverable"] is True
    assert out["session_id"] == created["session_id"]
