"""Database-backed worker leases for mining session advancement."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from services.factor_discovery.mining.errors import MiningConcurrencyConflictError, MiningSessionNotFoundError
from services.factor_discovery.mining.repositories import FactorMiningSessionRepository

DEFAULT_LEASE_SECONDS = 30


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class MiningLeaseService:
    def __init__(self, *, lease_seconds: int = DEFAULT_LEASE_SECONDS) -> None:
        self._sessions = FactorMiningSessionRepository()
        self._lease_seconds = lease_seconds

    def acquire(self, session_id: str, *, worker_id: str) -> str:
        row = self._sessions.get(session_id)
        if row is None:
            raise MiningSessionNotFoundError("SESSION_NOT_FOUND", session_id)
        now = _utcnow()
        if row.lease_token and row.lease_expires_at and row.lease_expires_at > now:
            if row.lease_owner_id != worker_id:
                raise MiningConcurrencyConflictError(
                    "LEASE_HELD",
                    f"{row.lease_owner_id} until {row.lease_expires_at.isoformat()}",
                )
            token = row.lease_token
        else:
            token = f"lease_{uuid.uuid4().hex[:16]}"
        expires = now + timedelta(seconds=self._lease_seconds)
        self._sessions.update_lease(
            session_id,
            lease_owner_id=worker_id,
            lease_token=token,
            lease_acquired_at=now,
            lease_expires_at=expires,
            last_heartbeat_at=now,
            expected_lease_version=row.lease_version,
        )
        return token

    def release(self, session_id: str, *, worker_id: str, lease_token: str) -> None:
        row = self._sessions.get(session_id)
        if row is None:
            return
        if row.lease_owner_id != worker_id or row.lease_token != lease_token:
            raise MiningConcurrencyConflictError("LEASE_MISMATCH", session_id)
        self._sessions.clear_lease(session_id, expected_lease_version=row.lease_version)

    def verify(self, session_id: str, *, worker_id: str, lease_token: str) -> None:
        row = self._sessions.get(session_id)
        if row is None:
            raise MiningSessionNotFoundError("SESSION_NOT_FOUND", session_id)
        now = _utcnow()
        if not row.lease_token or row.lease_owner_id != worker_id or row.lease_token != lease_token:
            raise MiningConcurrencyConflictError("LEASE_INVALID", session_id)
        if row.lease_expires_at and row.lease_expires_at < now:
            raise MiningConcurrencyConflictError("LEASE_EXPIRED", session_id)
