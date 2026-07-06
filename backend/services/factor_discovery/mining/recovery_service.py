"""Crash recovery for mining sessions."""
from __future__ import annotations

from services.factor_discovery.mining.errors import MiningRecoveryError
from services.factor_discovery.mining.models import MiningSessionStatus
from services.factor_discovery.mining.repositories import (
    FactorMiningEventRepository,
    FactorMiningSessionRepository,
)
from services.factor_discovery.repositories import FactorDiscoveryRunRepository


class MiningRecoveryService:
    def __init__(self) -> None:
        self._sessions = FactorMiningSessionRepository()
        self._events = FactorMiningEventRepository()
        self._runs = FactorDiscoveryRunRepository()

    def recover_session(self, session_id: str) -> dict:
        row = self._sessions.get(session_id)
        if row is None:
            raise MiningRecoveryError("SESSION_NOT_FOUND", session_id)
        if row.status in {
            MiningSessionStatus.COMPLETED.value,
            MiningSessionStatus.CANCELLED.value,
            MiningSessionStatus.BUDGET_EXHAUSTED.value,
            MiningSessionStatus.FAILED.value,
        }:
            raise MiningRecoveryError("SESSION_TERMINAL", row.status)

        events = self._events.list_for_session(session_id)
        last = events[-1] if events else None
        pending_run = None
        if last and last.run_id:
            pending_run = self._runs.get(last.run_id)

        return {
            "session_id": session_id,
            "status": row.status,
            "state_version": row.state_version,
            "last_event_type": last.event_type if last else None,
            "pending_run_id": pending_run.run_id if pending_run and pending_run.status == "running" else None,
            "pending_run_status": pending_run.status if pending_run else None,
            "recoverable": True,
        }
