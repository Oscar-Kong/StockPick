"""Repositories for Factor Discovery persistence."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from data.db_engine import get_engine
from engines.factor_discovery_models import (
    FactorDefinitionRecord,
    FactorDiscoveryAttempt,
    FactorDiscoveryRun,
    FactorHypothesisRecord,
    FactorResearchDataSnapshot,
    FactorResearchFamily,
    FactorSealedTestReceipt,
    FactorStatusEvent,
    FactorValidationArtifactRecord,
)
from models.schemas_factor_discovery import FactorDefinition, FactorHypothesis, FactorLifecycleStatus
from services.factor_discovery.data_provider import FactorResearchSnapshotRef
from services.factor_discovery.errors import FactorDefinitionConflictError, FactorDiscoveryError
from services.research_json import json_dumps, json_loads
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


class FactorHypothesisRepository:
    def create(self, hypothesis: FactorHypothesis, *, created_by: str, research_family_id: str | None = None) -> str:
        engine = get_engine()
        with Session(engine) as session:
            row = FactorHypothesisRecord(
                hypothesis_id=hypothesis.hypothesis_id,
                research_family_id=research_family_id,
                name=hypothesis.name,
                economic_rationale=hypothesis.economic_rationale,
                expected_mechanism=hypothesis.expected_mechanism,
                expected_direction=hypothesis.expected_direction.value,
                intended_universe=hypothesis.intended_universe,
                holding_period_sessions=hypothesis.holding_period_sessions,
                rebalance_frequency=hypothesis.rebalance_frequency,
                required_data_classes_json=json_dumps([c.value for c in hypothesis.required_data_classes]),
                known_risks_json=json_dumps(hypothesis.known_risks),
                expected_failure_conditions_json=json_dumps(hypothesis.expected_failure_conditions),
                tags_json=json_dumps(hypothesis.tags),
                creation_source=hypothesis.creation_source.value,
                schema_version=hypothesis.schema_version,
                created_by=created_by,
            )
            session.add(row)
            session.commit()
        return hypothesis.hypothesis_id

    def get(self, hypothesis_id: str) -> FactorHypothesisRecord | None:
        with Session(get_engine()) as session:
            return session.get(FactorHypothesisRecord, hypothesis_id)


class FactorResearchFamilyRepository:
    def create(
        self,
        *,
        research_objective: str,
        intended_universe: str,
        primary_horizon_sessions: int,
        data_source_policy_id: str,
        validation_config_family_id: str,
        created_by: str,
    ) -> str:
        family_id = _new_id("ffam")
        with Session(get_engine()) as session:
            session.add(
                FactorResearchFamily(
                    family_id=family_id,
                    research_objective=research_objective,
                    intended_universe=intended_universe,
                    primary_horizon_sessions=primary_horizon_sessions,
                    data_source_policy_id=data_source_policy_id,
                    validation_config_family_id=validation_config_family_id,
                    created_by=created_by,
                )
            )
            session.commit()
        return family_id

    def get(self, family_id: str) -> FactorResearchFamily | None:
        with Session(get_engine()) as session:
            return session.get(FactorResearchFamily, family_id)


class FactorDefinitionRepository:
    def create_version(self, definition: FactorDefinition, *, created_by: str, canonical_dsl: str, canonical_ast: dict) -> int:
        engine = get_engine()
        with Session(engine) as session:
            existing = (
                session.query(FactorDefinitionRecord)
                .filter(
                    FactorDefinitionRecord.factor_id == definition.factor_id,
                    FactorDefinitionRecord.version == definition.version,
                )
                .one_or_none()
            )
            if existing:
                if (
                    existing.formula_hash == definition.formula_hash()
                    and existing.definition_identity_hash == definition.definition_identity_hash()
                ):
                    return int(existing.id)
                raise FactorDefinitionConflictError(
                    "FACTOR_VERSION_CONFLICT",
                    f"factor {definition.factor_id} version {definition.version} already exists with different content",
                )
            row = FactorDefinitionRecord(
                factor_id=definition.factor_id,
                version=definition.version,
                hypothesis_id=definition.hypothesis_id,
                parent_factor_id=definition.parent_factor_id,
                parent_version=definition.parent_version,
                display_name=definition.display_name,
                original_dsl=canonical_dsl,
                canonical_dsl=canonical_dsl,
                canonical_ast_json=json_dumps(canonical_ast),
                formula_hash=definition.formula_hash(),
                definition_identity_hash=definition.definition_identity_hash(),
                expected_direction=definition.expected_direction.value,
                required_fields_json=json_dumps(definition.required_fields),
                data_source_policy_id=definition.data_source_policy_id,
                holding_period_sessions=definition.holding_period_sessions,
                rebalance_frequency=definition.rebalance_frequency,
                missing_value_policy=definition.missing_value_policy,
                outlier_policy=definition.outlier_policy,
                neutralization_keys_json=json_dumps([k.value for k in definition.neutralization_keys]),
                lifecycle_status=definition.lifecycle_status.value,
                created_by=created_by,
            )
            session.add(row)
            try:
                session.commit()
            except IntegrityError as exc:
                raise FactorDefinitionConflictError(
                    "FACTOR_VERSION_CONFLICT",
                    "duplicate factor version",
                ) from exc
            session.refresh(row)
            return int(row.id)

    def get(self, factor_id: str, version: str) -> FactorDefinitionRecord | None:
        with Session(get_engine()) as session:
            return (
                session.query(FactorDefinitionRecord)
                .filter(FactorDefinitionRecord.factor_id == factor_id, FactorDefinitionRecord.version == version)
                .one_or_none()
            )

    def update_cached_status(self, factor_id: str, version: str, status: FactorLifecycleStatus) -> None:
        with Session(get_engine()) as session:
            row = (
                session.query(FactorDefinitionRecord)
                .filter(FactorDefinitionRecord.factor_id == factor_id, FactorDefinitionRecord.version == version)
                .one_or_none()
            )
            if row is None:
                raise FactorDiscoveryError("FACTOR_DEFINITION_NOT_FOUND", f"{factor_id}@{version}")
            row.lifecycle_status = status.value
            session.commit()


class FactorDataSnapshotRepository:
    def upsert(self, ref: FactorResearchSnapshotRef, *, storage_reference: str | None = None) -> str:
        with Session(get_engine()) as session:
            row = session.get(FactorResearchDataSnapshot, ref.snapshot_id)
            if row is None:
                row = FactorResearchDataSnapshot(snapshot_id=ref.snapshot_id)
                session.add(row)
            row.provider_id = ref.provider_id
            row.data_source_policy_id = ref.data_source_policy_id
            row.universe_source = ref.universe_source
            row.universe_version = ref.universe_version
            row.universe_pit_evidence_json = json_dumps(ref.universe_pit_evidence)
            row.panel_hash = ref.panel_hash
            row.canonical_session_hash = ref.canonical_session_hash
            row.field_list_json = json_dumps(ref.field_list)
            row.field_provenance_summary_json = json_dumps(ref.field_provenance_summary)
            row.adjustment_status = ref.adjustment_status
            row.start_session = ref.start_session
            row.end_session = ref.end_session
            row.row_count = ref.row_count
            row.symbol_count = ref.symbol_count
            row.date_count = ref.date_count
            row.storage_reference = storage_reference or ref.storage_reference
            row.storage_format = ref.storage_format
            row.artifact_present = ref.artifact_present
            session.commit()
        return ref.snapshot_id

    def get(self, snapshot_id: str) -> FactorResearchDataSnapshot | None:
        with Session(get_engine()) as session:
            return session.get(FactorResearchDataSnapshot, snapshot_id)

    def get_by_identity(self, identity_hash: str) -> FactorResearchDataSnapshot | None:
        with Session(get_engine()) as session:
            return (
                session.query(FactorResearchDataSnapshot)
                .filter(FactorResearchDataSnapshot.snapshot_identity_hash == identity_hash)
                .one_or_none()
            )

    def set_identity(self, snapshot_id: str, identity_hash: str, *, provider_data_version: str | None = None) -> None:
        with Session(get_engine()) as session:
            row = session.get(FactorResearchDataSnapshot, snapshot_id)
            if row is None:
                raise FactorDiscoveryError("SNAPSHOT_NOT_FOUND", snapshot_id)
            row.snapshot_identity_hash = identity_hash
            if provider_data_version:
                row.provider_data_version = provider_data_version
            session.commit()


class FactorDiscoveryRunRepository:
    def create(self, **fields: Any) -> str:
        run_id = fields.pop("run_id", _new_id("fdrun"))
        with Session(get_engine()) as session:
            idem = fields.get("idempotency_key")
            payload_hash = fields.get("launch_payload_hash")
            if idem:
                existing = (
                    session.query(FactorDiscoveryRun)
                    .filter(FactorDiscoveryRun.idempotency_key == idem)
                    .one_or_none()
                )
                if existing:
                    if payload_hash and existing.launch_payload_hash and existing.launch_payload_hash != payload_hash:
                        from services.factor_discovery.errors import IdempotencyConflictError

                        raise IdempotencyConflictError(
                            "IDEMPOTENCY_PAYLOAD_MISMATCH",
                            f"idempotency key {idem} reused with different payload",
                        )
                    return existing.run_id
            row = FactorDiscoveryRun(run_id=run_id, **fields)
            session.add(row)
            try:
                session.commit()
            except IntegrityError as exc:
                session.rollback()
                if idem:
                    existing = (
                        session.query(FactorDiscoveryRun)
                        .filter(FactorDiscoveryRun.idempotency_key == idem)
                        .one_or_none()
                    )
                    if existing:
                        return existing.run_id
                raise exc
        return run_id

    def get_by_idempotency(self, key: str) -> FactorDiscoveryRun | None:
        with Session(get_engine()) as session:
            return session.query(FactorDiscoveryRun).filter(FactorDiscoveryRun.idempotency_key == key).one_or_none()

    def update(self, run_id: str, **fields: Any) -> None:
        with Session(get_engine()) as session:
            row = session.get(FactorDiscoveryRun, run_id)
            if row is None:
                raise FactorDiscoveryError("RUN_NOT_FOUND", run_id)
            for k, v in fields.items():
                setattr(row, k, v)
            session.commit()

    def get(self, run_id: str) -> FactorDiscoveryRun | None:
        with Session(get_engine()) as session:
            return session.get(FactorDiscoveryRun, run_id)


class FactorAttemptLedgerRepository:
    def append(self, **fields: Any) -> str:
        attempt_id = fields.pop("attempt_id", _new_id("fdatt"))
        with Session(get_engine()) as session:
            row = FactorDiscoveryAttempt(attempt_id=attempt_id, **fields)
            session.add(row)
            session.commit()
        return attempt_id

    def list_for_family(self, family_id: str) -> list[FactorDiscoveryAttempt]:
        with Session(get_engine()) as session:
            return (
                session.query(FactorDiscoveryAttempt)
                .filter(FactorDiscoveryAttempt.research_family_id == family_id)
                .order_by(FactorDiscoveryAttempt.created_at.asc())
                .all()
            )


class FactorValidationArtifactRepository:
    def create_closed(self, *, artifact_id: str | None = None, **fields: Any) -> str:
        aid = artifact_id or _new_id("fdart")
        fields.setdefault("open_state", "CLOSED")
        with Session(get_engine()) as session:
            existing = (
                session.query(FactorValidationArtifactRecord)
                .filter(FactorValidationArtifactRecord.validation_artifact_hash == fields["validation_artifact_hash"])
                .one_or_none()
            )
            if existing:
                return existing.artifact_id
            row = FactorValidationArtifactRecord(artifact_id=aid, **fields)
            session.add(row)
            try:
                session.commit()
            except IntegrityError:
                session.rollback()
                existing = (
                    session.query(FactorValidationArtifactRecord)
                    .filter(FactorValidationArtifactRecord.validation_artifact_hash == fields["validation_artifact_hash"])
                    .one()
                )
                return existing.artifact_id
        return aid

    def create_opened(self, *, closed_artifact_id: str, **fields: Any) -> str:
        aid = fields.pop("artifact_id", _new_id("fdart"))
        fields["open_state"] = "SEALED_OPENED"
        fields["closed_artifact_id"] = closed_artifact_id
        with Session(get_engine()) as session:
            row = FactorValidationArtifactRecord(artifact_id=aid, **fields)
            session.add(row)
            session.commit()
        return aid

    def get(self, artifact_id: str) -> FactorValidationArtifactRecord | None:
        with Session(get_engine()) as session:
            return session.get(FactorValidationArtifactRecord, artifact_id)

    def get_by_hash(self, artifact_hash: str) -> FactorValidationArtifactRecord | None:
        with Session(get_engine()) as session:
            return (
                session.query(FactorValidationArtifactRecord)
                .filter(FactorValidationArtifactRecord.validation_artifact_hash == artifact_hash)
                .one_or_none()
            )

    def link_revalidation(self, artifact_id: str, *, revalidation_of_artifact_id: str) -> None:
        with Session(get_engine()) as session:
            row = session.get(FactorValidationArtifactRecord, artifact_id)
            if row is None:
                raise FactorDiscoveryError("ARTIFACT_NOT_FOUND", artifact_id)
            row.revalidation_of_artifact_id = revalidation_of_artifact_id
            session.commit()


class FactorSealedReceiptRepository:
    def reserve(self, **fields: Any) -> str:
        receipt_id = fields.pop("receipt_id", _new_id("fdrct"))
        fields.setdefault("status", "RESERVED")
        with Session(get_engine()) as session:
            existing = self._find_identity(session, fields)
            if existing:
                if existing.status == "COMPLETED":
                    raise FactorDiscoveryError("SEALED_TEST_ALREADY_OPENED", existing.receipt_id)
                if existing.status == "FAILED":
                    raise FactorDiscoveryError("SEALED_RECEIPT_FAILED", existing.receipt_id)
                raise FactorDiscoveryError("SEALED_TEST_ALREADY_RESERVED", existing.receipt_id)
            row = FactorSealedTestReceipt(receipt_id=receipt_id, **fields)
            session.add(row)
            try:
                session.commit()
            except IntegrityError as exc:
                session.rollback()
                with Session(get_engine()) as session2:
                    existing = self._find_identity(session2, fields)
                    if existing:
                        if existing.status == "FAILED":
                            raise FactorDiscoveryError("SEALED_RECEIPT_FAILED", existing.receipt_id) from exc
                        code = "SEALED_TEST_ALREADY_OPENED" if existing.status == "COMPLETED" else "SEALED_TEST_ALREADY_RESERVED"
                        raise FactorDiscoveryError(code, existing.receipt_id) from exc
                raise
        return receipt_id

    def complete(self, receipt_id: str, *, opened_artifact_id: str) -> None:
        with Session(get_engine()) as session:
            row = session.get(FactorSealedTestReceipt, receipt_id)
            if row is None:
                raise FactorDiscoveryError("RECEIPT_NOT_FOUND", receipt_id)
            row.status = "COMPLETED"
            row.opened_artifact_id = opened_artifact_id
            row.completed_at = _utcnow()
            session.commit()

    def fail(self, receipt_id: str, *, failure_code: str) -> None:
        with Session(get_engine()) as session:
            row = session.get(FactorSealedTestReceipt, receipt_id)
            if row is None:
                raise FactorDiscoveryError("RECEIPT_NOT_FOUND", receipt_id)
            row.status = "FAILED"
            row.failure_code = failure_code
            row.completed_at = _utcnow()
            session.commit()

    def get(self, receipt_id: str) -> FactorSealedTestReceipt | None:
        with Session(get_engine()) as session:
            return session.get(FactorSealedTestReceipt, receipt_id)

    @staticmethod
    def _find_identity(session: Session, fields: dict[str, Any]) -> FactorSealedTestReceipt | None:
        return (
            session.query(FactorSealedTestReceipt)
            .filter(
                FactorSealedTestReceipt.factor_id == fields["factor_id"],
                FactorSealedTestReceipt.factor_version == fields["factor_version"],
                FactorSealedTestReceipt.formula_hash == fields["formula_hash"],
                FactorSealedTestReceipt.plan_hash == fields["plan_hash"],
                FactorSealedTestReceipt.panel_snapshot_id == fields["panel_snapshot_id"],
                FactorSealedTestReceipt.period_hash == fields["period_hash"],
                FactorSealedTestReceipt.validation_config_hash == fields["validation_config_hash"],
                FactorSealedTestReceipt.access_policy_version == fields["access_policy_version"],
            )
            .one_or_none()
        )


class FactorStatusEventRepository:
    def append(self, **fields: Any) -> str:
        event_id = fields.pop("event_id", _new_id("fdevt"))
        with Session(get_engine()) as session:
            session.add(FactorStatusEvent(event_id=event_id, **fields))
            session.commit()
        return event_id

    def list_for_factor(self, factor_id: str, version: str) -> list[FactorStatusEvent]:
        with Session(get_engine()) as session:
            return (
                session.query(FactorStatusEvent)
                .filter(FactorStatusEvent.factor_id == factor_id, FactorStatusEvent.factor_version == version)
                .order_by(FactorStatusEvent.created_at.asc())
                .all()
            )
