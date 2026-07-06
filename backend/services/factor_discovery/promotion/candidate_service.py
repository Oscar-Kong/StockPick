"""Promotion candidate CRUD, evidence, and governed transitions."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from config import FACTOR_MODEL_VERSION, STRATEGY_VERSION
from core.sleeve import normalize_sleeve
from data.db_engine import get_engine
from engines.audit.logger import audit_log
from engines.factor_discovery_models import (
    FactorDefinitionRecord,
    FactorPromotionCandidate,
    FactorPromotionStatusEvent,
)
from models.schemas_factor_promotion import (
    CreatePromotionCandidateRequest,
    EvidenceBundleDetail,
    FactorPromotionCandidateDetail,
    FactorPromotionCandidateListResponse,
    FactorPromotionCandidateSummary,
    FactorPromotionStatus,
    PromotionAuditEvent,
    PromotionAuditHistoryResponse,
    PromotionGateEvaluation,
    PromotionStatusTransitionRequest,
    PromotionStatusTransitionResponse,
)
from services.factor_discovery.errors import FactorDiscoveryError
from services.factor_discovery.promotion.evidence_bundle import FactorPromotionEvidenceService
from services.factor_discovery.promotion.gate_service import FactorPromotionGateService
from services.factor_discovery.promotion.lifecycle import requires_gate_pass, validate_transition
from services.research_json import json_dumps, json_loads
from sqlalchemy.orm import Session


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class FactorPromotionCandidateService:
    def __init__(self) -> None:
        self._evidence = FactorPromotionEvidenceService()
        self._gates = FactorPromotionGateService()

    def create(self, body: CreatePromotionCandidateRequest) -> FactorPromotionCandidateDetail:
        sleeve = normalize_sleeve(body.sleeve)
        if sleeve not in {"penny", "compounder"}:
            raise FactorDiscoveryError("INVALID_SLEEVE", f"unsupported sleeve: {body.sleeve}")

        with Session(get_engine()) as session:
            factor = (
                session.query(FactorDefinitionRecord)
                .filter(
                    FactorDefinitionRecord.factor_id == body.factor_id,
                    FactorDefinitionRecord.version == body.factor_version,
                )
                .one_or_none()
            )
            if factor is None:
                raise FactorDiscoveryError(
                    "FACTOR_NOT_FOUND", f"{body.factor_id}@{body.factor_version}"
                )
            existing = (
                session.query(FactorPromotionCandidate)
                .filter(
                    FactorPromotionCandidate.factor_id == body.factor_id,
                    FactorPromotionCandidate.factor_version == body.factor_version,
                    FactorPromotionCandidate.sleeve == sleeve,
                    FactorPromotionCandidate.status.notin_(["rejected", "archived"]),
                )
                .one_or_none()
            )
            if existing:
                raise FactorDiscoveryError(
                    "CANDIDATE_EXISTS", f"active candidate {existing.candidate_id} already exists"
                )

        staging = self._evidence.load_staging_report(body.source_staging_run_id)
        if staging and staging.get("promotion_readiness", {}).get("status") != "READY_FOR_PROMOTION_REVIEW":
            raise FactorDiscoveryError(
                "STAGING_NOT_READY",
                "extended staging must be READY_FOR_PROMOTION_REVIEW before creating candidates",
            )

        diagnostics, cell = self._best_diagnostics(staging, body.factor_id, sleeve)
        gate_eval = self._gates.evaluate(
            diagnostics=diagnostics,
            staging_report=staging,
            sleeve=sleeve,
        )
        factor_def = {
            "factor_id": factor.factor_id,
            "factor_version": factor.version,
            "display_name": factor.display_name,
            "sleeve": sleeve,
            "canonical_dsl": factor.canonical_dsl,
            "formula_hash": factor.formula_hash,
            "expected_direction": factor.expected_direction,
        }
        candidate_id = f"fpcand_{uuid.uuid4().hex[:12]}"
        bundle_id, bundle_hash, _detail = self._evidence.build_bundle(
            candidate_id=candidate_id,
            factor_definition=factor_def,
            diagnostics=diagnostics,
            gate_evaluation=gate_eval,
            staging_report=staging,
        )

        now = _utcnow()
        row = FactorPromotionCandidate(
            candidate_id=candidate_id,
            factor_id=factor.factor_id,
            factor_version=factor.version,
            display_name=factor.display_name,
            description=f"Promotion candidate from staging {body.source_staging_run_id or 'latest'}",
            formula_reference=factor.canonical_dsl,
            source_experiment_ids_json=json_dumps(body.source_experiment_ids),
            source_staging_run_id=body.source_staging_run_id or (staging or {}).get("staging_run_id"),
            sleeve=sleeve,
            expected_direction=factor.expected_direction,
            required_data_json=factor.required_fields_json,
            data_latency_class="daily",
            coverage_statistics_json=json_dumps(diagnostics.get("coverage") or cell.get("coverage") or {}),
            performance_metrics_json=json_dumps(
                {
                    "mean_rank_ic": diagnostics.get("mean_rank_ic"),
                    "acceptance_status": diagnostics.get("acceptance_status"),
                }
            ),
            robustness_summary_json=json_dumps(diagnostics.get("robustness_slices") or {}),
            transaction_cost_sensitivity_json=json_dumps(
                {"transaction_cost_impact_bps": diagnostics.get("transaction_cost_impact_bps")}
            ),
            known_weaknesses_json=json_dumps(
                (staging or {}).get("promotion_readiness", {}).get("weak_factors") or []
            ),
            status=FactorPromotionStatus.EXPERIMENTAL.value,
            status_reason=body.reason,
            evidence_bundle_id=bundle_id,
            evidence_bundle_hash=bundle_hash,
            gate_evaluation_json=json_dumps(gate_eval.model_dump(mode="json")),
            created_by=body.actor,
            created_at=now,
            updated_at=now,
        )
        with Session(get_engine()) as session:
            session.add(row)
            session.add(
                FactorPromotionStatusEvent(
                    event_id=f"fpsevt_{uuid.uuid4().hex[:12]}",
                    candidate_id=candidate_id,
                    previous_status=None,
                    new_status=FactorPromotionStatus.EXPERIMENTAL.value,
                    actor=body.actor,
                    reason=body.reason,
                    evidence_bundle_hash=bundle_hash,
                    created_at=now,
                )
            )
            session.commit()

        audit_log(
            "factor_promotion_candidate_created",
            sleeve=sleeve,
            payload={
                "candidate_id": candidate_id,
                "factor_id": factor.factor_id,
                "evidence_bundle_hash": bundle_hash,
                "no_live_mutation": True,
            },
        )
        return self.get(candidate_id)

    def list_candidates(
        self,
        *,
        sleeve: str | None = None,
        status: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> FactorPromotionCandidateListResponse:
        with Session(get_engine()) as session:
            q = session.query(FactorPromotionCandidate)
            if sleeve:
                q = q.filter(FactorPromotionCandidate.sleeve == normalize_sleeve(sleeve))
            if status:
                q = q.filter(FactorPromotionCandidate.status == status)
            total = q.count()
            rows = q.order_by(FactorPromotionCandidate.created_at.desc()).offset(offset).limit(limit).all()
        return FactorPromotionCandidateListResponse(
            items=[self._summary(r) for r in rows],
            total=total,
            offset=offset,
            limit=limit,
        )

    def get(self, candidate_id: str) -> FactorPromotionCandidateDetail:
        row = self._get_row(candidate_id)
        gate = None
        if row.gate_evaluation_json:
            gate = PromotionGateEvaluation.model_validate(json_loads(row.gate_evaluation_json, {}))
        return FactorPromotionCandidateDetail(
            **self._summary(row).model_dump(),
            description=row.description or "",
            formula_reference=row.formula_reference or "",
            required_data=json_loads(row.required_data_json, []),
            data_latency_class=row.data_latency_class,
            coverage_statistics=json_loads(row.coverage_statistics_json, {}),
            performance_metrics=json_loads(row.performance_metrics_json, {}),
            robustness_summary=json_loads(row.robustness_summary_json, {}),
            transaction_cost_sensitivity=json_loads(row.transaction_cost_sensitivity_json, {}),
            known_weaknesses=json_loads(row.known_weaknesses_json, []),
            version=row.version,
            status_reason=row.status_reason or "",
            latest_gate_evaluation=gate,
            change_proposal_id=row.change_proposal_id,
        )

    def transition(
        self, candidate_id: str, body: PromotionStatusTransitionRequest
    ) -> PromotionStatusTransitionResponse:
        row = self._get_row(candidate_id)
        current = FactorPromotionStatus(row.status)
        target = body.target_status
        if current == target:
            raise FactorDiscoveryError("NO_OP_TRANSITION", f"already in status {current.value}")
        validate_transition(current, target)

        if body.expected_evidence_bundle_hash and body.expected_evidence_bundle_hash != row.evidence_bundle_hash:
            raise FactorDiscoveryError("STALE_EVIDENCE", "evidence bundle hash mismatch — rebuild evidence first")

        gate = None
        if row.gate_evaluation_json:
            gate = PromotionGateEvaluation.model_validate(json_loads(row.gate_evaluation_json, {}))

        if requires_gate_pass(target) and target == FactorPromotionStatus.APPROVED_FOR_MANUAL_INTEGRATION:
            if gate is None or not gate.overall_pass:
                raise FactorDiscoveryError(
                    "GATES_NOT_PASS",
                    "cannot approve — blocking promotion gates failed",
                )
            if not row.evidence_bundle_hash:
                raise FactorDiscoveryError("MISSING_EVIDENCE", "evidence bundle required for approval")

        if target == FactorPromotionStatus.SHADOW and current == FactorPromotionStatus.PROMOTION_CANDIDATE:
            if gate is None:
                raise FactorDiscoveryError("MISSING_GATES", "gate evaluation required before shadow")

        now = _utcnow()
        event_id = f"fpsevt_{uuid.uuid4().hex[:12]}"
        with Session(get_engine()) as session:
            db_row = session.get(FactorPromotionCandidate, candidate_id)
            if db_row is None:
                raise FactorDiscoveryError("CANDIDATE_NOT_FOUND", candidate_id)
            db_row.status = target.value
            db_row.status_reason = body.reason
            db_row.reviewer = body.actor
            db_row.reviewed_at = now
            db_row.updated_at = now
            session.add(
                FactorPromotionStatusEvent(
                    event_id=event_id,
                    candidate_id=candidate_id,
                    previous_status=current.value,
                    new_status=target.value,
                    actor=body.actor,
                    reason=body.reason,
                    approval_source=body.actor if target == FactorPromotionStatus.APPROVED_FOR_MANUAL_INTEGRATION else None,
                    evidence_bundle_hash=row.evidence_bundle_hash,
                    created_at=now,
                )
            )
            session.commit()

        audit_id = audit_log(
            "factor_promotion_status_transition",
            sleeve=row.sleeve,
            payload={
                "candidate_id": candidate_id,
                "previous_status": current.value,
                "new_status": target.value,
                "reason": body.reason,
                "factor_model_version": FACTOR_MODEL_VERSION,
                "strategy_version": STRATEGY_VERSION,
                "no_live_mutation": True,
            },
        )
        return PromotionStatusTransitionResponse(
            candidate_id=candidate_id,
            previous_status=current,
            new_status=target,
            event_id=event_id,
            audit_id=audit_id,
        )

    def audit_history(self, candidate_id: str) -> PromotionAuditHistoryResponse:
        self._get_row(candidate_id)
        with Session(get_engine()) as session:
            rows = (
                session.query(FactorPromotionStatusEvent)
                .filter(FactorPromotionStatusEvent.candidate_id == candidate_id)
                .order_by(FactorPromotionStatusEvent.created_at.asc())
                .all()
            )
        return PromotionAuditHistoryResponse(
            candidate_id=candidate_id,
            events=[
                PromotionAuditEvent(
                    event_id=r.event_id,
                    candidate_id=r.candidate_id,
                    previous_status=r.previous_status,
                    new_status=r.new_status,
                    actor=r.actor,
                    reason=r.reason,
                    approval_source=r.approval_source,
                    created_at=r.created_at,
                )
                for r in rows
            ],
        )

    def get_evidence(self, candidate_id: str) -> EvidenceBundleDetail:
        row = self._get_row(candidate_id)
        if not row.evidence_bundle_id:
            raise FactorDiscoveryError("MISSING_EVIDENCE", "no evidence bundle for candidate")
        detail = self._evidence.load(row.evidence_bundle_id)
        if detail is None:
            raise FactorDiscoveryError("EVIDENCE_NOT_FOUND", row.evidence_bundle_id)
        return detail

    def explain(self, candidate_id: str) -> dict:
        detail = self.get_evidence(candidate_id)
        return {
            "candidate_id": candidate_id,
            "summary": detail.summary,
            "disclaimer": detail.llm_summary_disclaimer,
            "gates_unchanged": True,
            "status_unchanged": True,
            "gate_evaluation": detail.gate_evaluation.model_dump(mode="json") if detail.gate_evaluation else None,
        }

    def _get_row(self, candidate_id: str) -> FactorPromotionCandidate:
        with Session(get_engine()) as session:
            row = session.get(FactorPromotionCandidate, candidate_id)
        if row is None:
            raise FactorDiscoveryError("CANDIDATE_NOT_FOUND", candidate_id)
        return row

    def _summary(self, row: FactorPromotionCandidate) -> FactorPromotionCandidateSummary:
        gate_pass = None
        if row.gate_evaluation_json:
            gate = PromotionGateEvaluation.model_validate(json_loads(row.gate_evaluation_json, {}))
            gate_pass = gate.overall_pass
        return FactorPromotionCandidateSummary(
            candidate_id=row.candidate_id,
            factor_id=row.factor_id,
            factor_version=row.factor_version,
            display_name=row.display_name,
            sleeve=row.sleeve,
            status=FactorPromotionStatus(row.status),
            expected_direction=row.expected_direction,
            source_staging_run_id=row.source_staging_run_id,
            source_experiment_ids=json_loads(row.source_experiment_ids_json, []),
            evidence_bundle_hash=row.evidence_bundle_hash,
            gate_overall_pass=gate_pass,
            created_at=row.created_at,
            reviewed_at=row.reviewed_at,
            reviewer=row.reviewer,
        )

    @staticmethod
    def _best_diagnostics(staging: dict | None, factor_id: str, sleeve: str) -> tuple[dict, dict]:
        if not staging:
            return {"factor_id": factor_id, "acceptance_status": "UNKNOWN"}, {}
        best: dict = {"factor_id": factor_id}
        best_cell: dict = {}
        for cell in staging.get("cell_results", []):
            if cell.get("factor_id") != factor_id or cell.get("sleeve") != sleeve:
                continue
            diag = cell.get("diagnostics") or {}
            if not best_cell or (diag.get("observation_count") or {}).get("value", 0) >= (
                (best.get("observation_count") or {}).get("value") or 0
            ):
                best = {**diag, "coverage": cell.get("coverage"), "acceptance_status": cell.get("acceptance_status")}
                best_cell = cell
        return best, best_cell

    @staticmethod
    def verify_live_config_unchanged() -> dict:
        from engines.quant_models import FactorWeight
        from config import DYNAMIC_WEIGHTS_ENABLED

        with Session(get_engine()) as session:
            weight_count = session.query(FactorWeight).count()
        return {
            "factor_model_version": FACTOR_MODEL_VERSION,
            "strategy_version": STRATEGY_VERSION,
            "dynamic_weights_enabled": DYNAMIC_WEIGHTS_ENABLED,
            "factor_weight_rows": weight_count,
            "live_mutation": False,
        }
