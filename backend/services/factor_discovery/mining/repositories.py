"""Persistence for Factor Discovery mining sessions."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from data.db_engine import get_engine
from engines.factor_discovery_models import (
    FactorMiningEvaluation,
    FactorMiningEvent,
    FactorMiningExposure,
    FactorMiningLineage,
    FactorMiningRevisionProposal,
    FactorMiningSession,
)
from services.factor_discovery.mining.errors import MiningConcurrencyConflictError, MiningSessionNotFoundError
from services.research_json import json_dumps, json_loads
from sqlalchemy.orm import Session


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class FactorMiningSessionRepository:
    def create(self, **fields: Any) -> str:
        sid = fields.pop("session_id", f"fdmine_{uuid.uuid4().hex[:12]}")
        with Session(get_engine()) as session:
            session.add(FactorMiningSession(session_id=sid, **fields))
            session.commit()
        return sid

    def get(self, session_id: str) -> FactorMiningSession | None:
        with Session(get_engine()) as session:
            return session.get(FactorMiningSession, session_id)

    def list_sessions(
        self,
        *,
        research_family_id: str | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[FactorMiningSession]:
        with Session(get_engine()) as session:
            q = session.query(FactorMiningSession).order_by(FactorMiningSession.created_at.desc())
            if research_family_id:
                q = q.filter(FactorMiningSession.research_family_id == research_family_id)
            if status:
                q = q.filter(FactorMiningSession.status == status)
            return q.offset(offset).limit(limit).all()

    def transition(
        self,
        session_id: str,
        *,
        new_status: str,
        expected_version: int,
        **updates: Any,
    ) -> int:
        with Session(get_engine()) as session:
            row = session.get(FactorMiningSession, session_id)
            if row is None:
                raise MiningSessionNotFoundError("SESSION_NOT_FOUND", session_id)
            if row.state_version != expected_version:
                raise MiningConcurrencyConflictError(
                    "STATE_VERSION_CONFLICT",
                    f"expected {expected_version}, got {row.state_version}",
                )
            row.status = new_status
            row.state_version = expected_version + 1
            for k, v in updates.items():
                setattr(row, k, v)
            session.commit()
            return row.state_version

    def update_usage(self, session_id: str, usage: dict) -> None:
        with Session(get_engine()) as session:
            row = session.get(FactorMiningSession, session_id)
            if row is None:
                return
            row.usage_json = json_dumps(usage)
            session.commit()

    def update_summary(self, session_id: str, *, summary_json: str, summary_hash: str) -> None:
        with Session(get_engine()) as session:
            row = session.get(FactorMiningSession, session_id)
            if row is None:
                return
            row.summary_json = summary_json
            row.summary_hash = summary_hash
            session.commit()

    def update_lease(
        self,
        session_id: str,
        *,
        lease_owner_id: str,
        lease_token: str,
        lease_acquired_at: datetime,
        lease_expires_at: datetime,
        last_heartbeat_at: datetime,
        expected_lease_version: int,
    ) -> None:
        with Session(get_engine()) as session:
            row = session.get(FactorMiningSession, session_id)
            if row is None:
                raise MiningSessionNotFoundError("SESSION_NOT_FOUND", session_id)
            if row.lease_version != expected_lease_version:
                raise MiningConcurrencyConflictError("LEASE_VERSION_CONFLICT", str(expected_lease_version))
            row.lease_owner_id = lease_owner_id
            row.lease_token = lease_token
            row.lease_acquired_at = lease_acquired_at
            row.lease_expires_at = lease_expires_at
            row.last_heartbeat_at = last_heartbeat_at
            row.lease_version = expected_lease_version + 1
            session.commit()

    def clear_lease(self, session_id: str, *, expected_lease_version: int) -> None:
        with Session(get_engine()) as session:
            row = session.get(FactorMiningSession, session_id)
            if row is None:
                return
            if row.lease_version != expected_lease_version:
                raise MiningConcurrencyConflictError("LEASE_VERSION_CONFLICT", str(expected_lease_version))
            row.lease_owner_id = None
            row.lease_token = None
            row.lease_acquired_at = None
            row.lease_expires_at = None
            row.lease_version = expected_lease_version + 1
            session.commit()

    def set_pause_reason(self, session_id: str, reason: str | None) -> None:
        with Session(get_engine()) as session:
            row = session.get(FactorMiningSession, session_id)
            if row is None:
                return
            row.pause_reason = reason
            session.commit()


class FactorMiningEventRepository:
    def append(self, **fields: Any) -> str:
        eid = fields.pop("event_id", f"fdmevt_{uuid.uuid4().hex[:12]}")
        with Session(get_engine()) as session:
            session.add(FactorMiningEvent(event_id=eid, **fields))
            session.commit()
        return eid

    def list_for_session(self, session_id: str) -> list[FactorMiningEvent]:
        with Session(get_engine()) as session:
            return (
                session.query(FactorMiningEvent)
                .filter(FactorMiningEvent.session_id == session_id)
                .order_by(FactorMiningEvent.created_at.asc())
                .all()
            )


class FactorMiningLineageRepository:
    def create(self, **fields: Any) -> str:
        lid = fields.pop("lineage_id", f"fdmlin_{uuid.uuid4().hex[:12]}")
        with Session(get_engine()) as session:
            session.add(FactorMiningLineage(lineage_id=lid, **fields))
            session.commit()
        return lid

    def get(self, lineage_id: str) -> FactorMiningLineage | None:
        with Session(get_engine()) as session:
            return session.get(FactorMiningLineage, lineage_id)

    def list_for_session(self, session_id: str) -> list[FactorMiningLineage]:
        with Session(get_engine()) as session:
            return (
                session.query(FactorMiningLineage)
                .filter(FactorMiningLineage.session_id == session_id)
                .order_by(FactorMiningLineage.created_at.asc())
                .all()
            )

    def update(self, lineage_id: str, **fields: Any) -> None:
        with Session(get_engine()) as session:
            row = session.get(FactorMiningLineage, lineage_id)
            if row is None:
                return
            for k, v in fields.items():
                setattr(row, k, v)
            row.updated_at = _utcnow()
            session.commit()


class FactorMiningEvaluationRepository:
    def create(self, **fields: Any) -> str:
        eid = fields.pop("evaluation_id", f"fdmeval_{uuid.uuid4().hex[:12]}")
        with Session(get_engine()) as session:
            session.add(FactorMiningEvaluation(evaluation_id=eid, **fields))
            session.commit()
        return eid

    def get_by_formula(
        self,
        session_id: str,
        lineage_id: str,
        formula_hash: str,
        *,
        revision_round: int = 0,
    ) -> FactorMiningEvaluation | None:
        with Session(get_engine()) as session:
            return (
                session.query(FactorMiningEvaluation)
                .filter(
                    FactorMiningEvaluation.session_id == session_id,
                    FactorMiningEvaluation.lineage_id == lineage_id,
                    FactorMiningEvaluation.formula_hash == formula_hash,
                    FactorMiningEvaluation.revision_round == revision_round,
                )
                .one_or_none()
            )

    def list_for_session(self, session_id: str) -> list[FactorMiningEvaluation]:
        with Session(get_engine()) as session:
            return (
                session.query(FactorMiningEvaluation)
                .filter(FactorMiningEvaluation.session_id == session_id)
                .order_by(FactorMiningEvaluation.created_at.asc())
                .all()
            )

    def list_for_lineage(self, session_id: str, lineage_id: str) -> list[FactorMiningEvaluation]:
        with Session(get_engine()) as session:
            return (
                session.query(FactorMiningEvaluation)
                .filter(
                    FactorMiningEvaluation.session_id == session_id,
                    FactorMiningEvaluation.lineage_id == lineage_id,
                )
                .order_by(FactorMiningEvaluation.created_at.asc())
                .all()
            )


class FactorMiningExposureRepository:
    def record(self, **fields: Any) -> str:
        eid = fields.pop("exposure_id", f"fdmexp_{uuid.uuid4().hex[:12]}")
        fields.setdefault("reservation_status", "FINALIZED")
        with Session(get_engine()) as session:
            session.add(FactorMiningExposure(exposure_id=eid, **fields))
            session.commit()
        return eid

    def count_for_lineage(self, session_id: str, lineage_id: str) -> int:
        with Session(get_engine()) as session:
            return (
                session.query(FactorMiningExposure)
                .filter(
                    FactorMiningExposure.session_id == session_id,
                    FactorMiningExposure.lineage_id == lineage_id,
                    FactorMiningExposure.reservation_status != "CANCELLED",
                )
                .count()
            )

    def count_for_formula(self, session_id: str, formula_hash: str) -> int:
        with Session(get_engine()) as session:
            return (
                session.query(FactorMiningExposure)
                .filter(
                    FactorMiningExposure.session_id == session_id,
                    FactorMiningExposure.formula_hash == formula_hash,
                    FactorMiningExposure.reservation_status != "CANCELLED",
                )
                .count()
            )

    def count_for_session(self, session_id: str) -> int:
        with Session(get_engine()) as session:
            return (
                session.query(FactorMiningExposure)
                .filter(
                    FactorMiningExposure.session_id == session_id,
                    FactorMiningExposure.reservation_status != "CANCELLED",
                )
                .count()
            )

    def find_idempotent(
        self,
        *,
        session_id: str,
        llm_interaction_id: str | None,
        operation_type: str,
        context_tier: str,
    ) -> FactorMiningExposure | None:
        with Session(get_engine()) as session:
            q = session.query(FactorMiningExposure).filter(
                FactorMiningExposure.session_id == session_id,
                FactorMiningExposure.operation_type == operation_type,
                FactorMiningExposure.context_tier == context_tier,
            )
            if llm_interaction_id:
                q = q.filter(FactorMiningExposure.llm_interaction_id == llm_interaction_id)
            return q.one_or_none()

    def update(self, exposure_id: str, **fields: Any) -> None:
        with Session(get_engine()) as session:
            row = session.get(FactorMiningExposure, exposure_id)
            if row is None:
                return
            for k, v in fields.items():
                setattr(row, k, v)
            session.commit()


class FactorMiningRevisionProposalRepository:
    def create(self, **fields: Any) -> str:
        pid = fields.pop("proposal_id", f"fdmprop_{uuid.uuid4().hex[:12]}")
        with Session(get_engine()) as session:
            session.add(FactorMiningRevisionProposal(proposal_id=pid, **fields))
            session.commit()
        return pid

    def list_for_lineage(self, session_id: str, lineage_id: str) -> list[FactorMiningRevisionProposal]:
        with Session(get_engine()) as session:
            return (
                session.query(FactorMiningRevisionProposal)
                .filter(
                    FactorMiningRevisionProposal.session_id == session_id,
                    FactorMiningRevisionProposal.lineage_id == lineage_id,
                )
                .order_by(FactorMiningRevisionProposal.created_at.asc())
                .all()
            )

    def get(self, proposal_id: str) -> FactorMiningRevisionProposal | None:
        with Session(get_engine()) as session:
            return session.get(FactorMiningRevisionProposal, proposal_id)
