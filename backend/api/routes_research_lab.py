"""Quant Lab research foundation API — ideas, experiments, runs, evidence memory, proposals."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from config import QUANT_LAB_RESEARCH_API_ENABLED
from models.schemas_research import (
    ChangeProposalCreate,
    ChangeProposalListResponse,
    ChangeProposalResponse,
    ChangeProposalUpdate,
    EvidenceImpactEvaluation,
    EvidenceMemoryCreate,
    EvidenceMemoryListResponse,
    EvidenceMemoryResponse,
    EvidenceMemoryUpdate,
    FactorLineageListResponse,
    MajorEvidenceGateResult,
    ResearchExperimentCreate,
    ResearchExperimentListResponse,
    ResearchExperimentResponse,
    ResearchExperimentUpdate,
    ResearchIdeaCreate,
    ResearchIdeaListResponse,
    ResearchIdeaResponse,
    ResearchIdeaUpdate,
    ResearchOverviewResponse,
    GenerateIdeasRequest,
    GenerateIdeasResponse,
    ExperimentTemplatesResponse,
    ExperimentPresetsResponse,
    ExperimentValidateRequest,
    ExperimentValidationResponse,
    ExperimentJobResponse,
    ExperimentLaunchResponse,
    ResearchRunCompareResponse,
    ResearchRunListResponse,
    ResearchRunSummary,
)
from services.change_proposals_service import (
    create_proposal,
    delete_proposal,
    get_proposal,
    list_proposals,
    update_proposal,
)
from services.evidence_impact_policy import evaluate_evidence_impact
from services.evidence_memory_service import (
    create_evidence_memory,
    delete_evidence_memory,
    get_evidence_memory,
    list_evidence_memory,
    update_evidence_memory,
)
from services.factor_lineage_service import get_factor_lineage, record_factor_lineage, sync_lineage_from_ic_panel
from services.major_evidence_gate import evaluate_major_evidence_gate
from services.research_experiments_service import (
    create_experiment,
    delete_experiment,
    get_experiment,
    list_experiments,
    update_experiment,
)
from services.research_ideas_service import create_idea, delete_idea, get_idea, list_ideas, update_idea
from services.research_overview_service import get_research_overview
from services.research_idea_generation_service import duplicate_idea, generate_ideas_from_findings
from services.experiment_presets_service import list_presets, list_templates
from services.experiment_validation_service import validate_experiment
from services.experiment_launch_service import launch_experiment
from services.experiment_job_service import get_job
from services.research_run_service import (
    backfill_run_index,
    compare_runs,
    get_run,
    index_run_from_store,
    link_run_to_experiment,
    list_runs,
)

router = APIRouter(prefix="/api/v2/research", tags=["quant-lab-research"])


def _require_research_api() -> None:
    if not QUANT_LAB_RESEARCH_API_ENABLED:
        raise HTTPException(status_code=503, detail="QUANT_LAB_RESEARCH_API_ENABLED is false")


# --- Overview ---


@router.get("/overview", response_model=ResearchOverviewResponse)
def get_overview(sleeve: str | None = None):
    _require_research_api()
    from buckets import DEFAULT_BUCKET

    return get_research_overview(sleeve or DEFAULT_BUCKET)


@router.post("/ideas/generate", response_model=GenerateIdeasResponse)
def post_generate_ideas(body: GenerateIdeasRequest):
    _require_research_api()
    from buckets import DEFAULT_BUCKET

    overview = get_research_overview(body.sleeve or DEFAULT_BUCKET)
    findings = overview.findings if body.from_findings_only else overview.findings
    return generate_ideas_from_findings(findings, sleeve=body.sleeve, limit=body.limit)


@router.post("/ideas/{idea_id}/duplicate", response_model=ResearchIdeaResponse)
def post_duplicate_idea(idea_id: str):
    _require_research_api()
    row = duplicate_idea(idea_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"idea not found: {idea_id}")
    return row


# --- Ideas ---


@router.post("/ideas", response_model=ResearchIdeaResponse)
def post_idea(body: ResearchIdeaCreate):
    _require_research_api()
    try:
        return create_idea(body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/ideas", response_model=ResearchIdeaListResponse)
def get_ideas(
    status: str | None = None,
    sleeve: str | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    _require_research_api()
    return list_ideas(status=status, sleeve=sleeve, offset=offset, limit=limit)  # type: ignore[arg-type]


@router.get("/ideas/{idea_id}", response_model=ResearchIdeaResponse)
def get_idea_by_id(idea_id: str):
    _require_research_api()
    row = get_idea(idea_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"idea not found: {idea_id}")
    return row


@router.patch("/ideas/{idea_id}", response_model=ResearchIdeaResponse)
def patch_idea(idea_id: str, body: ResearchIdeaUpdate):
    _require_research_api()
    try:
        row = update_idea(idea_id, body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not row:
        raise HTTPException(status_code=404, detail=f"idea not found: {idea_id}")
    return row


@router.delete("/ideas/{idea_id}")
def remove_idea(idea_id: str):
    _require_research_api()
    if not delete_idea(idea_id):
        raise HTTPException(status_code=404, detail=f"idea not found: {idea_id}")
    return {"deleted": True, "id": idea_id}


# --- Experiments ---


@router.post("/experiments", response_model=ResearchExperimentResponse)
def post_experiment(body: ResearchExperimentCreate):
    _require_research_api()
    try:
        return create_experiment(body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/experiments", response_model=ResearchExperimentListResponse)
def get_experiments(
    idea_id: str | None = None,
    experiment_type: str | None = None,
    sleeve: str | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    _require_research_api()
    return list_experiments(
        idea_id=idea_id,
        experiment_type=experiment_type,  # type: ignore[arg-type]
        sleeve=sleeve,
        offset=offset,
        limit=limit,
    )


@router.get("/experiments/templates", response_model=ExperimentTemplatesResponse)
def get_experiment_templates():
    _require_research_api()
    return list_templates()


@router.get("/experiments/presets", response_model=ExperimentPresetsResponse)
def get_experiment_presets():
    _require_research_api()
    return list_presets()


@router.post("/experiments/validate", response_model=ExperimentValidationResponse)
def post_validate_experiment(body: ExperimentValidateRequest):
    _require_research_api()
    return validate_experiment(body)


@router.get("/experiments/jobs/{job_id}", response_model=ExperimentJobResponse)
def get_experiment_job(job_id: str):
    _require_research_api()
    row = get_job(job_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"job not found: {job_id}")
    return row


@router.get("/experiments/{experiment_id}", response_model=ResearchExperimentResponse)
def get_experiment_by_id(experiment_id: str):
    _require_research_api()
    row = get_experiment(experiment_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"experiment not found: {experiment_id}")
    return row


@router.patch("/experiments/{experiment_id}", response_model=ResearchExperimentResponse)
def patch_experiment(experiment_id: str, body: ResearchExperimentUpdate):
    _require_research_api()
    try:
        row = update_experiment(experiment_id, body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not row:
        raise HTTPException(status_code=404, detail=f"experiment not found: {experiment_id}")
    return row


@router.delete("/experiments/{experiment_id}")
def remove_experiment(experiment_id: str):
    _require_research_api()
    if not delete_experiment(experiment_id):
        raise HTTPException(status_code=404, detail=f"experiment not found: {experiment_id}")
    return {"deleted": True, "id": experiment_id}


@router.post("/experiments/{experiment_id}/launch", response_model=ExperimentLaunchResponse)
def post_launch_experiment(experiment_id: str):
    _require_research_api()
    try:
        return launch_experiment(experiment_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# --- Unified runs ---


@router.get("/runs", response_model=ResearchRunListResponse)
def get_runs(
    run_type: str | None = None,
    sleeve: str | None = None,
    status: str | None = None,
    experiment_id: str | None = None,
    idea_id: str | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    backfill: bool = Query(True),
):
    _require_research_api()
    return list_runs(
        run_type=run_type,
        sleeve=sleeve,
        status=status,
        experiment_id=experiment_id,
        idea_id=idea_id,
        offset=offset,
        limit=limit,
        backfill=backfill,
    )


@router.post("/runs/backfill")
def post_runs_backfill(limit: int = Query(200, ge=1, le=1000)):
    _require_research_api()
    return {"indexed": backfill_run_index(limit=limit)}


@router.get("/runs/compare", response_model=ResearchRunCompareResponse)
def get_runs_compare(run_ids: str = Query(..., description="Comma-separated run IDs")):
    _require_research_api()
    ids = [x.strip() for x in run_ids.split(",") if x.strip()]
    if len(ids) < 1:
        raise HTTPException(status_code=400, detail="run_ids required")
    return compare_runs(ids)


@router.get("/runs/{run_id}", response_model=ResearchRunSummary)
def get_run_by_id(run_id: str):
    _require_research_api()
    row = get_run(run_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"run not found: {run_id}")
    return row


@router.post("/runs/{run_id}/index", response_model=ResearchRunSummary)
def post_index_run(run_id: str, store: str | None = None):
    _require_research_api()
    row = index_run_from_store(run_id, store=store)
    if not row:
        raise HTTPException(status_code=404, detail=f"unable to index run: {run_id}")
    return row


@router.patch("/runs/{run_id}/link", response_model=ResearchRunSummary)
def patch_link_run(run_id: str, experiment_id: str | None = None, idea_id: str | None = None):
    _require_research_api()
    row = link_run_to_experiment(run_id, experiment_id, idea_id=idea_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"run not found: {run_id}")
    return row


# --- Evidence memory ---


@router.post("/evidence-memory", response_model=EvidenceMemoryResponse)
def post_evidence_memory(body: EvidenceMemoryCreate):
    _require_research_api()
    try:
        return create_evidence_memory(body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/evidence-memory", response_model=EvidenceMemoryListResponse)
def get_evidence_memory_list(
    symbol: str | None = None,
    run_id: str | None = None,
    experiment_id: str | None = None,
    evidence_impact: str | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    _require_research_api()
    return list_evidence_memory(
        symbol=symbol,
        run_id=run_id,
        experiment_id=experiment_id,
        evidence_impact=evidence_impact,  # type: ignore[arg-type]
        offset=offset,
        limit=limit,
    )


@router.get("/evidence-memory/{memory_id}", response_model=EvidenceMemoryResponse)
def get_evidence_memory_by_id(memory_id: int):
    _require_research_api()
    row = get_evidence_memory(memory_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"evidence memory not found: {memory_id}")
    return row


@router.patch("/evidence-memory/{memory_id}", response_model=EvidenceMemoryResponse)
def patch_evidence_memory(memory_id: int, body: EvidenceMemoryUpdate):
    _require_research_api()
    try:
        row = update_evidence_memory(memory_id, body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not row:
        raise HTTPException(status_code=404, detail=f"evidence memory not found: {memory_id}")
    return row


@router.delete("/evidence-memory/{memory_id}")
def remove_evidence_memory(memory_id: int):
    _require_research_api()
    if not delete_evidence_memory(memory_id):
        raise HTTPException(status_code=404, detail=f"evidence memory not found: {memory_id}")
    return {"deleted": True, "id": memory_id}


# --- Factor lineage ---


@router.get("/factor-lineage/{factor_id}", response_model=FactorLineageListResponse)
def get_factor_lineage_by_id(factor_id: str, sleeve: str | None = None, limit: int = Query(20, ge=1, le=100)):
    _require_research_api()
    return get_factor_lineage(factor_id, sleeve=sleeve, limit=limit)


@router.post("/factor-lineage/sync")
def post_factor_lineage_sync(sleeve: str, as_of_date: str):
    _require_research_api()
    count = sync_lineage_from_ic_panel(sleeve, as_of_date)
    return {"synced": count, "sleeve": sleeve, "as_of_date": as_of_date}


# --- Impact policy & gate (deterministic) ---


@router.post("/impact/evaluate", response_model=EvidenceImpactEvaluation)
def post_impact_evaluate(
    proposed_impact: str = Query("informational"),
    gate_review_required: bool = False,
    integrity_blocked: bool = False,
):
    _require_research_api()
    try:
        return evaluate_evidence_impact(
            proposed_impact=proposed_impact,  # type: ignore[arg-type]
            gate_review_required=gate_review_required,
            integrity_blocked=integrity_blocked,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/gate/evaluate", response_model=MajorEvidenceGateResult)
def post_gate_evaluate(run_id: str):
    _require_research_api()
    run = get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"run not found: {run_id}")
    return evaluate_major_evidence_gate(
        run_type=run.run_type,
        summary={m.label: m.value for m in run.primary_metrics},
        parameters=run.parameters,
        warnings=run.warnings,
        blockers=run.blockers,
    )


# --- Change proposals ---


@router.post("/change-proposals", response_model=ChangeProposalResponse)
def post_change_proposal(body: ChangeProposalCreate):
    _require_research_api()
    try:
        return create_proposal(body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/change-proposals", response_model=ChangeProposalListResponse)
def get_change_proposals(
    status: str | None = None,
    affected_sleeve: str | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    _require_research_api()
    return list_proposals(status=status, affected_sleeve=affected_sleeve, offset=offset, limit=limit)  # type: ignore[arg-type]


@router.get("/change-proposals/{proposal_id}", response_model=ChangeProposalResponse)
def get_change_proposal_by_id(proposal_id: str):
    _require_research_api()
    row = get_proposal(proposal_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"proposal not found: {proposal_id}")
    return row


@router.patch("/change-proposals/{proposal_id}", response_model=ChangeProposalResponse)
def patch_change_proposal(proposal_id: str, body: ChangeProposalUpdate):
    _require_research_api()
    try:
        row = update_proposal(proposal_id, body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not row:
        raise HTTPException(status_code=404, detail=f"proposal not found: {proposal_id}")
    return row


@router.delete("/change-proposals/{proposal_id}")
def remove_change_proposal(proposal_id: str):
    _require_research_api()
    if not delete_proposal(proposal_id):
        raise HTTPException(status_code=404, detail=f"proposal not found: {proposal_id}")
    return {"deleted": True, "id": proposal_id}
