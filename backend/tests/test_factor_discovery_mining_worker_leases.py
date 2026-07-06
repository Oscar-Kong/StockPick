"""Worker lease concurrency tests."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engines.quant_db import init_quant_db
from services.factor_discovery.mining.errors import MiningConcurrencyConflictError
from services.factor_discovery.mining.lease_service import MiningLeaseService
from services.factor_discovery.mining.session_service import FactorMiningSessionService
from tests.fixtures.factor_discovery.mining.helpers import authorize_and_start, enable_mining, mining_session_request


def test_lease_conflict_second_worker(isolated_backend_env, monkeypatch):
    init_quant_db()
    enable_mining(monkeypatch)
    created = FactorMiningSessionService().create_session(mining_session_request())
    authorize_and_start(FactorMiningSessionService(), created["session_id"])
    lease = MiningLeaseService()
    sid = created["session_id"]
    token_a = lease.acquire(sid, worker_id="worker_a")
    assert token_a
    with pytest.raises(MiningConcurrencyConflictError):
        lease.acquire(sid, worker_id="worker_b")
    lease.release(sid, worker_id="worker_a", lease_token=token_a)
    token_b = lease.acquire(sid, worker_id="worker_b")
    assert token_b
