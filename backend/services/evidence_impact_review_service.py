"""Evidence impact review queue and actions — no direct production weight updates."""
from __future__ import annotations

from typing import Any

from data.db_engine import get_engine
from engines.audit.logger import audit_log
from engines.quant_models import EvidenceMemory, ResearchRunIndex
from models.schemas_research import (
    ChangeProposalCreate,
    ChangeProposalUpdate,
    EvidenceImpact,
    EvidenceReviewActionRequest,
    EvidenceReviewActionResponse,
    EvidenceReviewFinding,
    EvidenceReviewListResponse,
    MajorEvidenceGateResult,
)
from services.change_proposals_service import create_proposal, update_proposal
from services.major_evidence_gate import evaluate_major_evidence_gate
from services.research_json import json_dumps, json_loads
from services.research_run_detail_service import load_detail_payload
from services.research_run_service import get_run
from sqlalchemy.orm import Session

REVIEW_IMPACTS: tuple[str, ...] = (
    "supporting",
    "contradicting",
    "major_positive",
    "major_negative",
    "integrity_blocker",
)


def _gate_for_run(run_id: str) -> MajorEvidenceGateResult | None:
    summary = get_run(run_id)
    if not summary:
        return None
    detail = load_detail_payload(summary)
    return evaluate_major_evidence_gate(
        run_type=summary.run_type,
        summary=detail,
        parameters=summary.parameters,
        warnings=summary.warnings,
        blockers=summary.blockers,
    )


def _review_history(finding_id: str) -> list[dict[str, Any]]:
    from engines.audit.logger import list_audit_logs

    events = list_audit_logs(limit=20, event_type="evidence_review")
    return [e for e in events if e.get("payload", {}).get("finding_id") == finding_id]


def list_review_findings(
    *,
    sleeve: str | None = None,
    evidence_impact: EvidenceImpact | None = None,
    limit: int = 50,
) -> EvidenceReviewListResponse:
    findings: list[EvidenceReviewFinding] = []
    engine = get_engine()

    with Session(engine) as session:
        q = session.query(ResearchRunIndex).filter(
            ResearchRunIndex.evidence_impact.in_(REVIEW_IMPACTS),
            ResearchRunIndex.archived == 0,
        )
        if sleeve:
            q = q.filter(ResearchRunIndex.sleeve == sleeve)
        if evidence_impact:
            q = q.filter(ResearchRunIndex.evidence_impact == evidence_impact)
        rows = q.order_by(ResearchRunIndex.completed_at.desc().nullslast()).limit(limit).all()
        for row in rows:
            gate = _gate_for_run(row.run_id)
            findings.append(
                EvidenceReviewFinding(
                    finding_id=row.run_id,
                    source_type="run",
                    title=row.name,
                    evidence_impact=row.evidence_impact,  # type: ignore[arg-type]
                    verdict=row.verdict,
                    sleeve=row.sleeve,
                    supporting_run_ids=[row.run_id],
                    gate=gate,
                    sample_size=row.sample_size,
                    review_required=True,
                    unresolved_warnings=json_loads(row.warnings_json, []),
                    model_versions={
                        "strategy_version": row.strategy_version or "",
                        "factor_model_version": row.factor_model_version or "",
                    },
                    review_history=_review_history(row.run_id),
                )
            )

        mem_q = session.query(EvidenceMemory).filter(EvidenceMemory.evidence_impact.in_(REVIEW_IMPACTS))
        if sleeve:
            mem_q = mem_q.filter(EvidenceMemory.symbol.isnot(None))
        for mem in mem_q.order_by(EvidenceMemory.updated_at.desc()).limit(limit).all():
            findings.append(
                EvidenceReviewFinding(
                    finding_id=f"mem_{mem.id}",
                    source_type="evidence_memory",
                    title=mem.deterministic_finding[:120] if mem.deterministic_finding else f"Evidence {mem.id}",
                    evidence_impact=mem.evidence_impact,  # type: ignore[arg-type]
                    verdict=mem.verdict,
                    sleeve=sleeve,
                    symbol=mem.symbol,
                    supporting_run_ids=[mem.run_id] if mem.run_id else [],
                    gate=None,
                    sample_size=None,
                    review_required=True,
                    unresolved_warnings=[],
                    model_versions={},
                    review_history=_review_history(f"mem_{mem.id}"),
                )
            )

    return EvidenceReviewListResponse(findings=findings[:limit], total=len(findings))


def apply_review_action(finding_id: str, body: EvidenceReviewActionRequest) -> EvidenceReviewActionResponse | None:
    run_id = finding_id if not finding_id.startswith("mem_") else None
    summary = get_run(run_id) if run_id else None
    current_impact: EvidenceImpact = summary.evidence_impact if summary else "informational"  # type: ignore[assignment]

    new_impact: EvidenceImpact = current_impact
    proposal_id: str | None = None

    if body.action == "leave_informational":
        new_impact = "informational"
    elif body.action == "acknowledge_supporting":
        new_impact = "supporting"
    elif body.action == "reject":
        new_impact = "informational"
    elif body.action == "create_validation_work":
        new_impact = current_impact
    elif body.action == "create_change_proposal":
        prop = create_proposal(
            ChangeProposalCreate(
                title=body.proposal_title or f"Proposal from {finding_id}",
                finding=body.notes or (summary.name if summary else finding_id),
                supporting_run_ids=[run_id] if run_id else [],
                affected_sleeve=summary.sleeve if summary else None,
                status="needs_validation",
            )
        )
        proposal_id = prop.id
        new_impact = current_impact
    elif body.action == "approve_for_staging":
        if proposal_id is None and run_id:
            prop = create_proposal(
                ChangeProposalCreate(
                    title=f"Staging approval for {run_id}",
                    finding=body.notes,
                    supporting_run_ids=[run_id],
                    affected_sleeve=summary.sleeve if summary else None,
                    status="approved_for_staging",
                )
            )
            proposal_id = prop.id
        new_impact = current_impact

    if run_id and summary:
        engine = get_engine()
        with Session(engine) as session:
            row = session.get(ResearchRunIndex, run_id)
            if row and body.action in ("leave_informational", "acknowledge_supporting", "reject"):
                row.evidence_impact = new_impact
                session.commit()

    audit_id = audit_log(
        "evidence_review",
        sleeve=summary.sleeve if summary else None,
        payload={
            "finding_id": finding_id,
            "action": body.action,
            "notes": body.notes,
            "impact_before": current_impact,
            "impact_after": new_impact,
            "proposal_id": proposal_id,
        },
    )

    if proposal_id and body.action == "approve_for_staging":
        update_proposal(proposal_id, ChangeProposalUpdate(status="approved_for_staging"))

    return EvidenceReviewActionResponse(
        finding_id=finding_id,
        action=body.action,
        evidence_impact=new_impact,
        proposal_id=proposal_id,
        audit_id=audit_id,
    )
