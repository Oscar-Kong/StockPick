"""Explicit Factor Discovery lifecycle transitions with audit events."""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from data.db_engine import get_engine
from engines.factor_discovery_models import FactorDefinitionRecord, FactorStatusEvent
from models.schemas_factor_discovery import FactorLifecycleStatus, validate_factor_status_transition
from services.factor_discovery.errors import FactorLifecycleError, ProductionPromotionError
from services.factor_discovery.repositories import FactorValidationArtifactRepository


@dataclass(frozen=True)
class LifecycleTransitionRequest:
    factor_id: str
    factor_version: str
    target_status: FactorLifecycleStatus
    actor_type: str
    actor_identifier: str
    reason: str
    evidence_artifact_id: str | None = None
    evidence_run_id: str | None = None
    evidence_opened_artifact_id: str | None = None
    approval_reference: str | None = None
    expected_formula_hash: str | None = None
    expected_plan_hash: str | None = None
    expected_panel_hash: str | None = None
    expected_session_hash: str | None = None
    expected_period_hash: str | None = None
    expected_config_hash: str | None = None


class FactorLifecycleService:
    def transition(self, req: LifecycleTransitionRequest) -> str:
        if req.target_status == FactorLifecycleStatus.PRODUCTION:
            raise ProductionPromotionError(
                "PRODUCTION_PROMOTION_NOT_AVAILABLE",
                "Production promotion requires ChangeProposal integration (Phase 6B)",
            )
        from sqlalchemy.orm import Session

        engine = get_engine()
        with Session(engine) as session:
            row = (
                session.query(FactorDefinitionRecord)
                .filter(
                    FactorDefinitionRecord.factor_id == req.factor_id,
                    FactorDefinitionRecord.version == req.factor_version,
                )
                .with_for_update()
                .one_or_none()
            )
            if row is None:
                raise FactorLifecycleError("FACTOR_DEFINITION_NOT_FOUND", f"{req.factor_id}@{req.factor_version}")
            current = FactorLifecycleStatus(row.lifecycle_status)
            if current == req.target_status:
                return current.value
            expected_version = int(getattr(row, "lifecycle_version", 0) or 0)
            validate_factor_status_transition(current, req.target_status)
            self._validate_evidence(req, current, row)
            event_id = f"fdevt_{uuid.uuid4().hex[:12]}"
            session.add(
                FactorStatusEvent(
                    event_id=event_id,
                    factor_id=req.factor_id,
                    factor_version=req.factor_version,
                    previous_status=current.value,
                    new_status=req.target_status.value,
                    actor_type=req.actor_type,
                    actor_identifier=req.actor_identifier,
                    reason=req.reason,
                    evidence_artifact_id=req.evidence_artifact_id,
                    evidence_run_id=req.evidence_run_id,
                    approval_reference=req.approval_reference,
                )
            )
            row.lifecycle_status = req.target_status.value
            row.lifecycle_version = expected_version + 1
            session.commit()
        return event_id

    def store_recommendation(self, factor_id: str, version: str, recommended: FactorLifecycleStatus | None) -> None:
        from sqlalchemy.orm import Session

        with Session(get_engine()) as session:
            row = (
                session.query(FactorDefinitionRecord)
                .filter(FactorDefinitionRecord.factor_id == factor_id, FactorDefinitionRecord.version == version)
                .one_or_none()
            )
            if row is None:
                return
            row.recommended_status = recommended.value if recommended else None
            session.commit()

    def _validate_evidence(
        self,
        req: LifecycleTransitionRequest,
        current: FactorLifecycleStatus,
        row: FactorDefinitionRecord,
    ) -> None:
        if current == FactorLifecycleStatus.DRAFT and req.target_status == FactorLifecycleStatus.COMPILED:
            if not req.expected_formula_hash or req.expected_formula_hash != row.formula_hash:
                raise FactorLifecycleError("FORMULA_HASH_MISMATCH", "compile evidence hash mismatch")
        if req.target_status == FactorLifecycleStatus.VALIDATED:
            if req.actor_type != "human":
                raise FactorLifecycleError("MISSING_HUMAN_APPROVAL", "VALIDATED requires human actor")
            if not req.approval_reference or not req.reason.strip():
                raise FactorLifecycleError("MISSING_APPROVAL", "VALIDATED requires approval_reference and reason")
            if not req.evidence_artifact_id or not req.evidence_run_id or not req.evidence_opened_artifact_id:
                raise FactorLifecycleError("MISSING_EVIDENCE", "VALIDATED requires closed and opened artifacts")
            closed = FactorValidationArtifactRepository().get(req.evidence_artifact_id)
            opened = FactorValidationArtifactRepository().get(req.evidence_opened_artifact_id)
            if closed is None or opened is None or closed.open_state != "CLOSED" or opened.open_state != "SEALED_OPENED":
                raise FactorLifecycleError("INVALID_EVIDENCE", "closed/opened artifact pair invalid")
            if req.expected_formula_hash and req.expected_formula_hash != closed.formula_hash:
                raise FactorLifecycleError("FORMULA_HASH_MISMATCH", "validation evidence formula mismatch")
            if req.expected_plan_hash and req.expected_plan_hash != closed.plan_hash:
                raise FactorLifecycleError("PLAN_HASH_MISMATCH", "validation evidence plan mismatch")
            if closed.acceptance_status != "PASS":
                raise FactorLifecycleError("ACCEPTANCE_NOT_PASS", "closed artifact acceptance must pass")

    def recommend_status_from_artifact(self, acceptance_status: str) -> FactorLifecycleStatus | None:
        if acceptance_status == "PASS":
            return FactorLifecycleStatus.PROMISING
        return None
