"""Quant Lab research foundation API — ideas, experiments, runs, evidence memory, proposals."""
from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Query

from config import QUANT_LAB_RESEARCH_API_ENABLED
from models.schemas_factor_promotion import (
    CreatePromotionCandidateRequest,
    PromotionReadinessResponse,
    PromotionStatusTransitionRequest,
    ShadowEvaluationListResponse,
    ShadowEvaluationRequest,
)
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
    ResearchRunCompareDetailResponse,
    ResearchRunCompareResponse,
    ResearchRunDetailResponse,
    ResearchRunDuplicateExperimentResponse,
    ResearchRunFollowUpIdeaRequest,
    ResearchRunArchiveRequest,
    ResearchRunListItem,
    ResearchRunListResponse,
    ResearchRunNoteRequest,
    ResearchRunSummary,
    ModelMonitorResponse,
    EvidenceReviewListResponse,
    EvidenceReviewActionRequest,
    EvidenceReviewActionResponse,
    JobRetryResponse,
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
    index_run_from_store,
    link_run_to_experiment,
    refresh_run_from_store,
)
from services import research_run_repository as run_repo
from services.research_results_service import (
    archive_run,
    create_follow_up_idea,
    duplicate_experiment_from_run,
    set_run_notes,
)
from services.research_run_export_service import export_csv, export_json
from services.evidence_memory_sync_service import resolve_outcomes_from_feedback, sync_evidence_from_run
from services.model_monitor_service import get_model_monitor
from services.evidence_impact_review_service import apply_review_action, list_review_findings
from services.job_retry_service import retry_research_job

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
    verdict: str | None = None,
    evidence_impact: str | None = None,
    experiment_id: str | None = None,
    idea_id: str | None = None,
    search: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    archived: bool | None = Query(False),
    include_archived: bool = Query(False),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    backfill: bool = Query(True),
):
    _require_research_api()
    archived_filter = None if include_archived else archived
    return run_repo.list_index(
        run_type=run_type,
        sleeve=sleeve,
        status=status,
        verdict=verdict,
        evidence_impact=evidence_impact,
        experiment_id=experiment_id,
        idea_id=idea_id,
        search=search,
        date_from=date_from,
        date_to=date_to,
        archived=archived_filter,
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
    return run_repo.compare(ids)


@router.get("/runs/compare/detail", response_model=ResearchRunCompareDetailResponse)
def get_runs_compare_detail(run_ids: str = Query(..., description="Comma-separated run IDs (2–4)")):
    _require_research_api()
    ids = [x.strip() for x in run_ids.split(",") if x.strip()]
    if len(ids) < 2:
        raise HTTPException(status_code=400, detail="at least two run_ids required")
    if len(ids) > 4:
        raise HTTPException(status_code=400, detail="at most four run_ids allowed")
    return run_repo.compare_detail(ids)


@router.get("/runs/{run_id}/detail", response_model=ResearchRunDetailResponse)
def get_run_detail_by_id(run_id: str, refresh: bool = Query(False)):
    _require_research_api()
    row = run_repo.get_detail(run_id, refresh=refresh, use_llm=False)
    if not row:
        raise HTTPException(status_code=404, detail=f"run not found: {run_id}")
    return row


@router.get("/runs/{run_id}/export")
def get_run_export(run_id: str, format: str = Query("json", pattern="^(json|csv)$"), refresh: bool = Query(False)):
    _require_research_api()
    if format == "csv":
        body = export_csv(run_id, refresh=refresh)
        if body is None:
            raise HTTPException(status_code=404, detail=f"run not found: {run_id}")
        from fastapi.responses import PlainTextResponse

        return PlainTextResponse(body, media_type="text/csv")
    body = export_json(run_id, refresh=refresh)
    if body is None:
        raise HTTPException(status_code=404, detail=f"run not found: {run_id}")
    from fastapi.responses import JSONResponse

    return JSONResponse(content=json.loads(body))


@router.patch("/runs/{run_id}/notes", response_model=ResearchRunListItem)
def patch_run_notes(run_id: str, body: ResearchRunNoteRequest):
    _require_research_api()
    row = set_run_notes(run_id, body.notes)
    if not row:
        raise HTTPException(status_code=404, detail=f"run not found: {run_id}")
    return row


@router.patch("/runs/{run_id}/archive", response_model=ResearchRunListItem)
def patch_run_archive(run_id: str, body: ResearchRunArchiveRequest):
    _require_research_api()
    row = archive_run(run_id, archived=body.archived)
    if not row:
        raise HTTPException(status_code=404, detail=f"run not found: {run_id}")
    return row


@router.post("/runs/{run_id}/duplicate-experiment", response_model=ResearchRunDuplicateExperimentResponse)
def post_duplicate_experiment(run_id: str):
    _require_research_api()
    row = duplicate_experiment_from_run(run_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"run not found: {run_id}")
    return row


@router.post("/runs/{run_id}/follow-up-idea", response_model=ResearchRunSummary)
def post_follow_up_idea(run_id: str, body: ResearchRunFollowUpIdeaRequest):
    _require_research_api()
    row = create_follow_up_idea(run_id, title=body.title, hypothesis=body.hypothesis)
    if not row:
        raise HTTPException(status_code=404, detail=f"run not found: {run_id}")
    return row


@router.post("/runs/{run_id}/refresh", response_model=ResearchRunListItem)
def post_refresh_run(run_id: str, store: str | None = None):
    _require_research_api()
    row = refresh_run_from_store(run_id, store=store)
    if not row:
        raise HTTPException(status_code=404, detail=f"unable to refresh run: {run_id}")
    return row


@router.post("/runs/{run_id}/sync-evidence")
def post_sync_evidence(run_id: str):
    _require_research_api()
    created = sync_evidence_from_run(run_id)
    return {"synced": len(created), "items": created}


@router.post("/runs/{run_id}/resolve-outcomes")
def post_resolve_outcomes(run_id: str):
    _require_research_api()
    updated = resolve_outcomes_from_feedback(run_id)
    return {"updated": len(updated), "items": updated}


@router.get("/runs/{run_id}", response_model=ResearchRunSummary)
def get_run_by_id(run_id: str):
    _require_research_api()
    row = run_repo.get_summary(run_id)
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
    run = run_repo.get_summary(run_id)
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


# --- Model Monitor ---


@router.get("/model-monitor", response_model=ModelMonitorResponse)
def get_model_monitor_view(sleeve: str | None = None):
    _require_research_api()
    from buckets import DEFAULT_BUCKET

    return get_model_monitor(sleeve or DEFAULT_BUCKET)


@router.get("/evidence-review", response_model=EvidenceReviewListResponse)
def get_evidence_review(
    sleeve: str | None = None,
    evidence_impact: str | None = None,
    limit: int = Query(50, ge=1, le=200),
):
    _require_research_api()
    return list_review_findings(sleeve=sleeve, evidence_impact=evidence_impact, limit=limit)  # type: ignore[arg-type]


@router.post("/evidence-review/{finding_id}/action", response_model=EvidenceReviewActionResponse)
def post_evidence_review_action(finding_id: str, body: EvidenceReviewActionRequest):
    _require_research_api()
    row = apply_review_action(finding_id, body)
    if not row:
        raise HTTPException(status_code=404, detail=f"finding not found: {finding_id}")
    return row


@router.post("/jobs/{job_id}/retry", response_model=JobRetryResponse)
def post_retry_job(job_id: str):
    _require_research_api()
    return retry_research_job(job_id)


# --- Factor Discovery (Phase 5 — gated; no frontend) ---


@router.post("/factor-discovery/hypotheses")
def post_factor_hypothesis(body: dict):
    _require_research_api()
    from config import FACTOR_DISCOVERY_ENABLED
    from models.schemas_factor_discovery import FactorHypothesis
    from services.factor_discovery.repositories import FactorHypothesisRepository

    if not FACTOR_DISCOVERY_ENABLED:
        raise HTTPException(status_code=503, detail="FACTOR_DISCOVERY_ENABLED is false")
    hypothesis = FactorHypothesis.model_validate(body)
    hid = FactorHypothesisRepository().create(hypothesis, created_by=body.get("created_by", "api"))
    return {"hypothesis_id": hid}


@router.post("/factor-discovery/definitions")
def post_factor_definition(body: dict):
    _require_research_api()
    from config import FACTOR_DISCOVERY_ENABLED
    from engines.factor.discovery.formatter import format_factor_expression
    from engines.factor.discovery.parser import parse_factor_expression
    from models.schemas_factor_discovery import FactorDefinition
    from services.factor_discovery.repositories import FactorDefinitionRepository

    if not FACTOR_DISCOVERY_ENABLED:
        raise HTTPException(status_code=503, detail="FACTOR_DISCOVERY_ENABLED is false")
    definition = FactorDefinition.model_validate(body)
    dsl = format_factor_expression(definition.expression)
    FactorDefinitionRepository().create_version(
        definition,
        created_by=body.get("created_by", "api"),
        canonical_dsl=dsl,
        canonical_ast=definition.expression.model_dump(mode="json"),
    )
    return {
        "factor_id": definition.factor_id,
        "version": definition.version,
        "formula_hash": definition.formula_hash(),
    }


@router.post("/factor-discovery/families")
def post_factor_research_family(body: dict):
    _require_research_api()
    from config import FACTOR_DISCOVERY_ENABLED
    from services.factor_discovery.repositories import FactorResearchFamilyRepository

    if not FACTOR_DISCOVERY_ENABLED:
        raise HTTPException(status_code=503, detail="FACTOR_DISCOVERY_ENABLED is false")
    family_id = FactorResearchFamilyRepository().create(
        research_objective=str(body["research_objective"]),
        intended_universe=str(body["intended_universe"]),
        primary_horizon_sessions=int(body["primary_horizon_sessions"]),
        data_source_policy_id=str(body.get("data_source_policy_id", "research_adjusted_daily_v1")),
        validation_config_family_id=str(body.get("validation_config_family_id", "default_v1")),
        created_by=str(body.get("created_by", "api")),
    )
    return {"family_id": family_id}


@router.post("/factor-discovery/lifecycle/transition")
def post_factor_lifecycle_transition(body: dict):
    _require_research_api()
    from config import FACTOR_DISCOVERY_ENABLED
    from models.schemas_factor_discovery import FactorLifecycleStatus
    from services.factor_discovery.lifecycle_service import FactorLifecycleService, LifecycleTransitionRequest

    if not FACTOR_DISCOVERY_ENABLED:
        raise HTTPException(status_code=503, detail="FACTOR_DISCOVERY_ENABLED is false")
    req = LifecycleTransitionRequest(
        factor_id=str(body["factor_id"]),
        factor_version=str(body["factor_version"]),
        target_status=FactorLifecycleStatus(body["target_status"]),
        actor_type=str(body.get("actor_type", "human")),
        actor_identifier=str(body.get("actor_identifier", "api")),
        reason=str(body.get("reason", "")),
        evidence_artifact_id=body.get("evidence_artifact_id"),
        evidence_run_id=body.get("evidence_run_id"),
        approval_reference=body.get("approval_reference"),
        expected_formula_hash=body.get("expected_formula_hash"),
    )
    event_id = FactorLifecycleService().transition(req)
    return {"event_id": event_id}


@router.post("/factor-discovery/sealed-test/open")
def post_factor_sealed_test_open(body: dict):
    _require_research_api()
    from config import FACTOR_DISCOVERY_ENABLED
    from engines.factor.discovery.validation_models import SealedTestAccess
    from services.factor_discovery.errors import FactorDiscoveryError, SealedTestReservationError
    from services.factor_discovery.sealed_test_service import FactorSealedTestService, SealedOpenRequest

    if not FACTOR_DISCOVERY_ENABLED:
        raise HTTPException(status_code=503, detail="FACTOR_DISCOVERY_ENABLED is false")
    access = SealedTestAccess.model_validate(body["access"])
    try:
        result = FactorSealedTestService().open_sealed_test(
            SealedOpenRequest(
                run_id=str(body["run_id"]),
                access=access,
                sealed_data_commitment_hash=str(body["sealed_data_commitment_hash"]),
            )
        )
    except SealedTestReservationError as exc:
        raise HTTPException(status_code=409, detail={"code": exc.code, "message": exc.message}) from exc
    except FactorDiscoveryError as exc:
        raise HTTPException(status_code=400, detail={"code": exc.code, "message": exc.message}) from exc
    return result


# --- Factor Discovery LLM (Phase 6B — gated; no frontend) ---


def _require_factor_discovery_llm():
    _require_research_api()
    from config import FACTOR_DISCOVERY_LLM_ENABLED

    if not bool(FACTOR_DISCOVERY_LLM_ENABLED):
        raise HTTPException(status_code=503, detail="FACTOR_DISCOVERY_LLM_ENABLED is false")


@router.post("/factor-discovery/llm/hypotheses/generate")
def post_llm_generate_hypotheses(body: dict):
    _require_factor_discovery_llm()
    from services.factor_discovery.llm.errors import FactorLlmError
    from services.factor_discovery.llm.hypothesis_service import FactorHypothesisGenerationService
    from services.factor_discovery.llm.models import FactorResearchRequest

    try:
        payload = dict(body)
        family_id = str(payload.pop("research_family_id"))
        idempotency_key = payload.pop("idempotency_key", None)
        req = FactorResearchRequest.model_validate(payload)
        return FactorHypothesisGenerationService().generate(
            req,
            research_family_id=family_id,
            idempotency_key=idempotency_key,
        )
    except FactorLlmError as exc:
        raise HTTPException(status_code=400, detail={"code": exc.code, "message": exc.message}) from exc


@router.post("/factor-discovery/llm/hypotheses/{candidate_id}/critique")
def post_llm_critique_hypothesis(candidate_id: str, body: dict | None = None):
    _require_factor_discovery_llm()
    from services.factor_discovery.llm.hypothesis_critic_service import FactorHypothesisCriticService

    body = body or {}
    return FactorHypothesisCriticService().critique(candidate_id, actor=str(body.get("actor", "api")))


@router.post("/factor-discovery/llm/hypotheses/{candidate_id}/approve")
def post_llm_approve_hypothesis(candidate_id: str, body: dict):
    _require_factor_discovery_llm()
    from services.factor_discovery.llm.errors import FactorLlmReviewConflictError
    from services.factor_discovery.llm.review_service import FactorLlmReviewService

    try:
        FactorLlmReviewService().approve_hypothesis(
            candidate_id,
            actor=str(body.get("actor", "api")),
            reason=str(body.get("reason", "")),
        )
    except FactorLlmReviewConflictError as exc:
        raise HTTPException(status_code=409, detail={"code": exc.code, "message": exc.message}) from exc
    return {"candidate_id": candidate_id, "review_status": "APPROVED"}


@router.post("/factor-discovery/llm/hypotheses/{candidate_id}/reject")
def post_llm_reject_hypothesis(candidate_id: str, body: dict):
    _require_factor_discovery_llm()
    from services.factor_discovery.llm.review_service import FactorLlmReviewService

    FactorLlmReviewService().reject_hypothesis(
        candidate_id, actor=str(body.get("actor", "api")), reason=str(body.get("reason", ""))
    )
    return {"candidate_id": candidate_id, "review_status": "REJECTED"}


@router.post("/factor-discovery/llm/hypotheses/{candidate_id}/formulas/generate")
def post_llm_translate_formula(candidate_id: str, body: dict | None = None):
    _require_factor_discovery_llm()
    from services.factor_discovery.llm.errors import FactorLlmError
    from services.factor_discovery.llm.formula_translation_service import FactorFormulaTranslationService

    body = body or {}
    try:
        return FactorFormulaTranslationService().translate(
            candidate_id, actor=str(body.get("actor", "api"))
        )
    except FactorLlmError as exc:
        raise HTTPException(status_code=400, detail={"code": exc.code, "message": exc.message}) from exc


@router.post("/factor-discovery/llm/formulas/{candidate_id}/review")
def post_llm_review_formula(candidate_id: str, body: dict | None = None):
    _require_factor_discovery_llm()
    from services.factor_discovery.llm.formula_review_service import FactorFormulaReviewService

    body = body or {}
    return FactorFormulaReviewService().review(candidate_id, actor=str(body.get("actor", "api")))


@router.post("/factor-discovery/llm/formulas/{candidate_id}/approve")
def post_llm_approve_formula(candidate_id: str, body: dict):
    _require_factor_discovery_llm()
    from services.factor_discovery.llm.definition_service import FactorDefinitionFromLlmService
    from services.factor_discovery.llm.errors import FactorLlmReviewConflictError
    from services.factor_discovery.llm.review_service import FactorLlmReviewService

    try:
        FactorLlmReviewService().approve_formula(
            candidate_id, actor=str(body.get("actor", "api")), reason=str(body.get("reason", ""))
        )
        return FactorDefinitionFromLlmService().create_definition(
            candidate_id,
            factor_id=body.get("factor_id"),
            version=str(body.get("version", "1.0.0")),
            actor=str(body.get("actor", "api")),
            reason=str(body.get("reason", "")),
        )
    except FactorLlmReviewConflictError as exc:
        raise HTTPException(status_code=409, detail={"code": exc.code, "message": exc.message}) from exc


@router.post("/factor-discovery/llm/formulas/{candidate_id}/reject")
def post_llm_reject_formula(candidate_id: str, body: dict):
    _require_factor_discovery_llm()
    from services.factor_discovery.llm.review_service import FactorLlmReviewService

    FactorLlmReviewService().reject_formula(
        candidate_id, actor=str(body.get("actor", "api")), reason=str(body.get("reason", ""))
    )
    return {"candidate_id": candidate_id, "review_status": "REJECTED"}


@router.post("/factor-discovery/llm/runs/{run_id}/interpret")
def post_llm_interpret_run(run_id: str, body: dict | None = None):
    _require_factor_discovery_llm()
    from services.factor_discovery.llm.errors import FactorLlmError
    from services.factor_discovery.llm.interpretation_service import FactorRunInterpretationService

    body = body or {}
    try:
        return FactorRunInterpretationService().interpret(
            run_id,
            actor=str(body.get("actor", "api")),
            include_opened_sealed=bool(body.get("include_opened_sealed", False)),
        )
    except FactorLlmError as exc:
        raise HTTPException(status_code=400, detail={"code": exc.code, "message": exc.message}) from exc


@router.get("/factor-discovery/llm/interactions/{interaction_id}")
def get_llm_interaction(interaction_id: str):
    _require_factor_discovery_llm()
    from services.factor_discovery.errors import FactorDiscoveryError
    from services.factor_discovery.llm.interaction_detail_service import FactorLlmInteractionDetailService

    try:
        return FactorLlmInteractionDetailService().get_detail(interaction_id)
    except FactorDiscoveryError as exc:
        raise HTTPException(status_code=404, detail={"code": exc.code, "message": exc.message}) from exc


@router.get("/factor-discovery/llm/candidates")
def list_llm_candidates(
    research_family_id: str | None = Query(default=None),
    candidate_type: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    _require_factor_discovery_llm()
    from services.factor_discovery.llm.candidate_repository import FactorLlmCandidateRepository

    rows = FactorLlmCandidateRepository().list_for_family(
        research_family_id or "",
        candidate_type=candidate_type,
        limit=limit,
        offset=offset,
    ) if research_family_id else []
    return {
        "items": [
            {
                "candidate_id": r.candidate_id,
                "candidate_type": r.candidate_type,
                "review_status": r.review_status,
                "validation_status": r.validation_status,
                "interaction_id": r.interaction_id,
            }
            for r in rows
        ]
    }


# --- Factor Discovery Mining Loop (Phase 7) ---


def _require_factor_discovery_mining():
    _require_research_api()
    from config import FACTOR_DISCOVERY_LOOP_ENABLED

    if not bool(FACTOR_DISCOVERY_LOOP_ENABLED):
        raise HTTPException(status_code=503, detail="FACTOR_DISCOVERY_LOOP_ENABLED is false")


def _handle_mining_error(exc: Exception) -> None:
    from services.factor_discovery.llm.errors import FactorLlmReviewConflictError
    from services.factor_discovery.mining.errors import FactorMiningError, MiningConcurrencyConflictError
    from services.factor_discovery.mining.mutation_helpers import mining_http_status_for_error
    from services.factor_discovery.mining.repositories import FactorMiningSessionRepository

    if isinstance(exc, MiningConcurrencyConflictError):
        latest = None
        parts = str(exc.message).split("got ")
        if len(parts) == 2:
            try:
                latest = int(parts[1].strip())
            except ValueError:
                latest = None
        raise HTTPException(
            status_code=409,
            detail={"code": exc.code, "message": exc.message, "state_version": latest},
        ) from exc
    if isinstance(exc, FactorLlmReviewConflictError):
        raise HTTPException(status_code=409, detail={"code": exc.code, "message": exc.message}) from exc
    if isinstance(exc, FactorMiningError):
        status = mining_http_status_for_error(exc.code)
        detail: dict = {"code": exc.code, "message": exc.message}
        if exc.code == "STATE_VERSION_CONFLICT" and isinstance(exc, MiningConcurrencyConflictError):
            row = FactorMiningSessionRepository().get(str(getattr(exc, "session_id", "")))
            if row:
                detail["state_version"] = row.state_version
        raise HTTPException(status_code=status, detail=detail) from exc
    raise exc


def _parse_mining_state_version(body: dict) -> int:
    from services.factor_discovery.mining.errors import MiningSessionStateError
    from services.factor_discovery.mining.mutation_helpers import parse_expected_state_version

    try:
        return parse_expected_state_version(body)
    except MiningSessionStateError as exc:
        raise HTTPException(status_code=422, detail={"code": exc.code, "message": exc.message}) from exc


@router.get("/factor-discovery/staging/preflight")
def get_factor_discovery_staging_preflight():
    _require_research_api()
    from services.factor_discovery.staging.preflight_service import FactorDiscoveryStagingPreflightService

    return FactorDiscoveryStagingPreflightService().run(allow_test=True)


@router.get("/factor-discovery/staging/latest-audit")
def get_factor_discovery_latest_staging_audit():
    _require_research_api()
    from services.factor_discovery.staging.audit_artifact import FactorDiscoveryStagingAuditArtifact

    artifact = FactorDiscoveryStagingAuditArtifact().latest()
    if artifact is None:
        raise HTTPException(status_code=404, detail={"code": "STAGING_AUDIT_NOT_FOUND", "message": "No staging audit artifact"})
    return artifact


@router.get("/factor-discovery/staging/extended-latest")
def get_factor_discovery_extended_staging_latest():
    _require_research_api()
    from services.factor_discovery.staging.extended_staging_artifact import ExtendedStagingArtifactStore

    artifact = ExtendedStagingArtifactStore().latest()
    if artifact is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "EXTENDED_STAGING_NOT_FOUND", "message": "No extended staging report"},
        )
    return artifact


def _require_promotion_governance() -> None:
    from config import FACTOR_PROMOTION_GOVERNANCE_ENABLED

    if not FACTOR_PROMOTION_GOVERNANCE_ENABLED:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "PROMOTION_GOVERNANCE_DISABLED",
                "message": "FACTOR_PROMOTION_GOVERNANCE_ENABLED is false",
            },
        )


@router.get("/factor-discovery/promotion/readiness")
def get_factor_promotion_readiness():
    _require_research_api()
    from config import FACTOR_PROMOTION_GOVERNANCE_ENABLED, FACTOR_SHADOW_SCORING_ENABLED
    from services.factor_discovery.promotion.candidate_service import FactorPromotionCandidateService

    live = FactorPromotionCandidateService.verify_live_config_unchanged()
    return PromotionReadinessResponse(
        governance_enabled=FACTOR_PROMOTION_GOVERNANCE_ENABLED,
        shadow_scoring_enabled=FACTOR_SHADOW_SCORING_ENABLED,
        live_config_mutated=live.get("live_mutation", False),
    )


@router.get("/factor-discovery/promotion-candidates")
def list_promotion_candidates(
    sleeve: str | None = None,
    status: str | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
):
    _require_research_api()
    _require_promotion_governance()
    from services.factor_discovery.errors import FactorDiscoveryError
    from services.factor_discovery.promotion.candidate_service import FactorPromotionCandidateService

    try:
        return FactorPromotionCandidateService().list_candidates(
            sleeve=sleeve, status=status, offset=offset, limit=limit
        )
    except FactorDiscoveryError as exc:
        raise HTTPException(status_code=400, detail={"code": exc.code, "message": exc.message}) from exc


@router.post("/factor-discovery/promotion-candidates")
def create_promotion_candidate(body: CreatePromotionCandidateRequest):
    _require_research_api()
    _require_promotion_governance()
    from services.factor_discovery.errors import FactorDiscoveryError
    from services.factor_discovery.promotion.candidate_service import FactorPromotionCandidateService

    try:
        return FactorPromotionCandidateService().create(body)
    except FactorDiscoveryError as exc:
        status = 409 if exc.code == "CANDIDATE_EXISTS" else 400
        raise HTTPException(status_code=status, detail={"code": exc.code, "message": exc.message}) from exc


@router.get("/factor-discovery/promotion-candidates/{candidate_id}")
def get_promotion_candidate(candidate_id: str):
    _require_research_api()
    _require_promotion_governance()
    from services.factor_discovery.errors import FactorDiscoveryError
    from services.factor_discovery.promotion.candidate_service import FactorPromotionCandidateService

    try:
        return FactorPromotionCandidateService().get(candidate_id)
    except FactorDiscoveryError as exc:
        raise HTTPException(status_code=404, detail={"code": exc.code, "message": exc.message}) from exc


@router.post("/factor-discovery/promotion-candidates/{candidate_id}/transitions")
def transition_promotion_candidate(candidate_id: str, body: PromotionStatusTransitionRequest):
    _require_research_api()
    _require_promotion_governance()
    from services.factor_discovery.errors import FactorDiscoveryError
    from services.factor_discovery.promotion.candidate_service import FactorPromotionCandidateService

    try:
        return FactorPromotionCandidateService().transition(candidate_id, body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"code": "ILLEGAL_TRANSITION", "message": str(exc)}) from exc
    except FactorDiscoveryError as exc:
        raise HTTPException(status_code=400, detail={"code": exc.code, "message": exc.message}) from exc


@router.get("/factor-discovery/promotion-candidates/{candidate_id}/evidence")
def get_promotion_candidate_evidence(candidate_id: str):
    _require_research_api()
    _require_promotion_governance()
    from services.factor_discovery.errors import FactorDiscoveryError
    from services.factor_discovery.promotion.candidate_service import FactorPromotionCandidateService

    try:
        return FactorPromotionCandidateService().get_evidence(candidate_id)
    except FactorDiscoveryError as exc:
        raise HTTPException(status_code=404, detail={"code": exc.code, "message": exc.message}) from exc


@router.get("/factor-discovery/promotion-candidates/{candidate_id}/audit")
def get_promotion_candidate_audit(candidate_id: str):
    _require_research_api()
    _require_promotion_governance()
    from services.factor_discovery.errors import FactorDiscoveryError
    from services.factor_discovery.promotion.candidate_service import FactorPromotionCandidateService

    try:
        return FactorPromotionCandidateService().audit_history(candidate_id)
    except FactorDiscoveryError as exc:
        raise HTTPException(status_code=404, detail={"code": exc.code, "message": exc.message}) from exc


@router.post("/factor-discovery/promotion-candidates/{candidate_id}/explain")
def explain_promotion_candidate(candidate_id: str):
    _require_research_api()
    _require_promotion_governance()
    from services.factor_discovery.errors import FactorDiscoveryError
    from services.factor_discovery.promotion.candidate_service import FactorPromotionCandidateService

    try:
        return FactorPromotionCandidateService().explain(candidate_id)
    except FactorDiscoveryError as exc:
        raise HTTPException(status_code=404, detail={"code": exc.code, "message": exc.message}) from exc


@router.post("/factor-discovery/promotion-candidates/{candidate_id}/shadow-evaluations")
def request_shadow_evaluation(candidate_id: str, body: ShadowEvaluationRequest):
    _require_research_api()
    _require_promotion_governance()
    from config import FACTOR_SHADOW_SCORING_ENABLED
    from services.factor_discovery.errors import FactorDiscoveryError
    from services.factor_discovery.promotion.candidate_service import FactorPromotionCandidateService
    from services.factor_discovery.promotion.shadow_scoring import FactorShadowScoringService

    if not FACTOR_SHADOW_SCORING_ENABLED:
        raise HTTPException(
            status_code=503,
            detail={"code": "SHADOW_SCORING_DISABLED", "message": "FACTOR_SHADOW_SCORING_ENABLED is false"},
        )
    try:
        row = FactorPromotionCandidateService()._get_row(candidate_id)
        if row.status not in {"shadow", "promotion_candidate", "approved_for_manual_integration"}:
            raise FactorDiscoveryError(
                "INVALID_STATUS_FOR_SHADOW",
                "shadow evaluation requires promotion_candidate or shadow status",
            )
        return FactorShadowScoringService().evaluate(
            candidate_row=row,
            as_of_date=body.as_of_date,
            symbols=body.symbols,
            shadow_weight=body.shadow_weight,
            actor=body.actor,
        )
    except FactorDiscoveryError as exc:
        raise HTTPException(status_code=400, detail={"code": exc.code, "message": exc.message}) from exc


@router.get("/factor-discovery/promotion-candidates/{candidate_id}/shadow-evaluations")
def list_shadow_evaluations(candidate_id: str, limit: int = Query(default=20, ge=1, le=100)):
    _require_research_api()
    _require_promotion_governance()
    from services.factor_discovery.errors import FactorDiscoveryError
    from services.factor_discovery.promotion.candidate_service import FactorPromotionCandidateService
    from services.factor_discovery.promotion.shadow_scoring import FactorShadowScoringService

    try:
        FactorPromotionCandidateService()._get_row(candidate_id)
        runs = FactorShadowScoringService().list_runs(candidate_id, limit=limit)
        return ShadowEvaluationListResponse(candidate_id=candidate_id, runs=runs, total=len(runs))
    except FactorDiscoveryError as exc:
        raise HTTPException(status_code=404, detail={"code": exc.code, "message": exc.message}) from exc


@router.get("/factor-discovery/mining/readiness")
def get_mining_readiness():
    _require_research_api()
    from services.factor_discovery.mining.readiness_service import factor_discovery_mining_readiness

    return factor_discovery_mining_readiness()


@router.get("/factor-discovery/families")
def list_factor_research_families(limit: int = Query(default=50, ge=1, le=200)):
    _require_research_api()
    from config import FACTOR_DISCOVERY_ENABLED
    from data.db_engine import get_engine
    from engines.factor_discovery_models import FactorMiningSession, FactorResearchFamily
    from sqlalchemy.orm import Session

    if not FACTOR_DISCOVERY_ENABLED:
        raise HTTPException(status_code=503, detail="FACTOR_DISCOVERY_ENABLED is false")
    with Session(get_engine()) as session:
        rows = session.query(FactorResearchFamily).order_by(FactorResearchFamily.created_at.desc()).limit(limit).all()
        attempt_counts: dict[str, int] = {}
        for r in rows:
            attempt_counts[r.family_id] = (
                session.query(FactorMiningSession)
                .filter(FactorMiningSession.research_family_id == r.family_id)
                .count()
            )
    return {
        "items": [
            {
                "family_id": r.family_id,
                "research_objective": r.research_objective,
                "intended_universe": r.intended_universe,
                "primary_horizon_sessions": r.primary_horizon_sessions,
                "closed": bool(r.closed),
                "formula_attempt_count": attempt_counts.get(r.family_id, 0),
                "multiple_testing_policy": r.attempt_count_policy_version,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
    }


@router.post("/factor-discovery/mining/sessions")
def post_mining_session(body: dict):
    _require_factor_discovery_mining()
    from services.factor_discovery.mining.models import FactorMiningSessionCreateRequest
    from services.factor_discovery.mining.session_service import FactorMiningSessionService

    req = FactorMiningSessionCreateRequest.model_validate(body)
    return FactorMiningSessionService().create_session(req)


@router.post("/factor-discovery/mining/sessions/{session_id}/authorize")
def post_mining_authorize(session_id: str, body: dict):
    _require_factor_discovery_mining()
    from services.factor_discovery.mining.session_service import FactorMiningSessionService

    try:
        return FactorMiningSessionService().authorize_session(
            session_id,
            actor=str(body.get("actor", "api")),
            reason=str(body.get("reason", "")),
            state_version=_parse_mining_state_version(body),
        )
    except HTTPException:
        raise
    except Exception as exc:
        _handle_mining_error(exc)


@router.post("/factor-discovery/mining/sessions/{session_id}/start")
def post_mining_start(session_id: str, body: dict):
    _require_factor_discovery_mining()
    from services.factor_discovery.mining.session_service import FactorMiningSessionService

    try:
        return FactorMiningSessionService().start_session(
            session_id,
            actor=str(body.get("actor", "api")),
            state_version=_parse_mining_state_version(body),
        )
    except HTTPException:
        raise
    except Exception as exc:
        _handle_mining_error(exc)


@router.post("/factor-discovery/mining/sessions/{session_id}/advance")
def post_mining_advance(session_id: str, body: dict | None = None):
    _require_factor_discovery_mining()
    from services.factor_discovery.mining.errors import FactorMiningError, MiningConcurrencyConflictError
    from services.factor_discovery.mining.orchestrator import FactorMiningOrchestrator

    body = body or {}
    try:
        expected = _parse_mining_state_version(body)
        result = FactorMiningOrchestrator().advance(
            session_id,
            maximum_steps=int(body.get("maximum_steps", 1)),
            actor=str(body.get("actor", "api")),
            expected_state_version=expected,
        ).model_dump(mode="json")
        from services.factor_discovery.mining.session_detail_service import FactorMiningSessionDetailService

        envelope = FactorMiningSessionDetailService().mutation_envelope(
            session_id,
            prior_status=result.get("prior_status"),
            events_created=result.get("events", []),
        )
        return {**envelope, **result}
    except HTTPException:
        raise
    except MiningConcurrencyConflictError as exc:
        _handle_mining_error(exc)
    except FactorMiningError as exc:
        _handle_mining_error(exc)


@router.post("/factor-discovery/mining/sessions/{session_id}/pause")
def post_mining_pause(session_id: str, body: dict):
    _require_factor_discovery_mining()
    from services.factor_discovery.mining.session_service import FactorMiningSessionService

    try:
        return FactorMiningSessionService().pause_session(
            session_id,
            actor=str(body.get("actor", "api")),
            reason=str(body.get("reason", "")),
            state_version=_parse_mining_state_version(body),
        )
    except HTTPException:
        raise
    except Exception as exc:
        _handle_mining_error(exc)


@router.post("/factor-discovery/mining/sessions/{session_id}/resume")
def post_mining_resume(session_id: str, body: dict):
    _require_factor_discovery_mining()
    from services.factor_discovery.mining.session_service import FactorMiningSessionService

    try:
        return FactorMiningSessionService().resume_session(
            session_id,
            actor=str(body.get("actor", "api")),
            resume_to=str(body.get("resume_to", "GENERATING_HYPOTHESES")),
            state_version=_parse_mining_state_version(body),
        )
    except HTTPException:
        raise
    except Exception as exc:
        _handle_mining_error(exc)


@router.post("/factor-discovery/mining/sessions/{session_id}/cancel")
def post_mining_cancel(session_id: str, body: dict):
    _require_factor_discovery_mining()
    from services.factor_discovery.mining.session_service import FactorMiningSessionService

    try:
        return FactorMiningSessionService().cancel_session(
            session_id,
            actor=str(body.get("actor", "api")),
            reason=str(body.get("reason", "")),
            state_version=_parse_mining_state_version(body),
        )
    except HTTPException:
        raise
    except Exception as exc:
        _handle_mining_error(exc)


@router.post("/factor-discovery/mining/sessions/{session_id}/hypotheses/{candidate_id}/approve")
def post_mining_approve_hypothesis(session_id: str, candidate_id: str, body: dict):
    _require_factor_discovery_mining()
    from services.factor_discovery.mining.session_service import FactorMiningSessionService

    try:
        return FactorMiningSessionService().approve_hypothesis(
            session_id,
            candidate_id,
            actor=str(body.get("actor", "api")),
            reason=str(body.get("reason", "")),
            state_version=_parse_mining_state_version(body),
        )
    except HTTPException:
        raise
    except Exception as exc:
        _handle_mining_error(exc)


@router.post("/factor-discovery/mining/sessions/{session_id}/hypotheses/{candidate_id}/reject")
def post_mining_reject_hypothesis(session_id: str, candidate_id: str, body: dict):
    _require_factor_discovery_mining()
    from services.factor_discovery.mining.session_service import FactorMiningSessionService

    try:
        return FactorMiningSessionService().reject_hypothesis(
            session_id,
            candidate_id,
            actor=str(body.get("actor", "api")),
            reason=str(body.get("reason", "")),
            state_version=_parse_mining_state_version(body),
        )
    except HTTPException:
        raise
    except Exception as exc:
        _handle_mining_error(exc)


@router.post("/factor-discovery/mining/sessions/{session_id}/formulas/{candidate_id}/approve")
def post_mining_approve_formula(session_id: str, candidate_id: str, body: dict):
    _require_factor_discovery_mining()
    from services.factor_discovery.mining.session_service import FactorMiningSessionService

    try:
        return FactorMiningSessionService().approve_formula(
            session_id,
            candidate_id,
            actor=str(body.get("actor", "api")),
            reason=str(body.get("reason", "")),
            state_version=_parse_mining_state_version(body),
        )
    except HTTPException:
        raise
    except Exception as exc:
        _handle_mining_error(exc)


@router.post("/factor-discovery/mining/sessions/{session_id}/formulas/{candidate_id}/reject")
def post_mining_reject_formula(session_id: str, candidate_id: str, body: dict):
    _require_factor_discovery_mining()
    from services.factor_discovery.mining.session_service import FactorMiningSessionService

    try:
        return FactorMiningSessionService().reject_formula(
            session_id,
            candidate_id,
            actor=str(body.get("actor", "api")),
            reason=str(body.get("reason", "")),
            state_version=_parse_mining_state_version(body),
        )
    except HTTPException:
        raise
    except Exception as exc:
        _handle_mining_error(exc)


@router.post("/factor-discovery/mining/sessions/{session_id}/revisions/{candidate_id}/approve")
def post_mining_approve_revision(session_id: str, candidate_id: str, body: dict):
    _require_factor_discovery_mining()
    from services.factor_discovery.mining.session_service import FactorMiningSessionService

    try:
        return FactorMiningSessionService().approve_revision(
            session_id,
            candidate_id,
            actor=str(body.get("actor", "api")),
            reason=str(body.get("reason", "")),
            state_version=_parse_mining_state_version(body),
        )
    except HTTPException:
        raise
    except Exception as exc:
        _handle_mining_error(exc)


@router.post("/factor-discovery/mining/sessions/{session_id}/revisions/{candidate_id}/reject")
def post_mining_reject_revision(session_id: str, candidate_id: str, body: dict):
    _require_factor_discovery_mining()
    from services.factor_discovery.mining.session_service import FactorMiningSessionService

    try:
        return FactorMiningSessionService().reject_revision(
            session_id,
            candidate_id,
            actor=str(body.get("actor", "api")),
            reason=str(body.get("reason", "")),
            state_version=_parse_mining_state_version(body),
        )
    except HTTPException:
        raise
    except Exception as exc:
        _handle_mining_error(exc)


@router.get("/factor-discovery/mining/sessions")
def list_mining_sessions(
    research_family_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    session_mode: str | None = Query(default=None),
    awaiting_review: bool = Query(default=False),
    promising_only: bool = Query(default=False),
    failed_only: bool = Query(default=False),
    search: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    _require_factor_discovery_mining()
    from services.factor_discovery.mining.budget_service import load_usage
    from services.factor_discovery.mining.models import LineageStatus, MiningSessionStatus
    from services.factor_discovery.mining.repositories import (
        FactorMiningLineageRepository,
        FactorMiningSessionRepository,
    )
    from services.factor_discovery.mining.mutation_helpers import count_pending_reviews
    from services.research_json import json_loads

    rows = FactorMiningSessionRepository().list_sessions(
        research_family_id=research_family_id,
        status=status,
        limit=limit,
        offset=offset,
    )
    lineages_repo = FactorMiningLineageRepository()
    items = []
    for r in rows:
        if session_mode and r.session_mode != session_mode:
            continue
        if failed_only and r.status != MiningSessionStatus.FAILED.value:
            continue
        lineages = lineages_repo.list_for_session(r.session_id)
        pending = count_pending_reviews(r.session_id, status=r.status)
        pending_total = pending["hypotheses"] + pending["formulas"] + pending["revisions"]
        promising = sum(1 for l in lineages if l.status == LineageStatus.PROMISING_FOR_HUMAN_REVIEW.value)
        if awaiting_review and pending_total == 0 and promising == 0:
            continue
        if promising_only and promising == 0:
            continue
        if search:
            needle = search.lower()
            if needle not in r.session_id.lower() and needle not in r.research_objective.lower():
                continue
        usage = load_usage(r.usage_json)
        items.append(
            {
                "session_id": r.session_id,
                "session_name": json_loads(r.normalized_request_json, {}).get("session_name"),
                "research_objective": r.research_objective,
                "status": r.status,
                "session_mode": r.session_mode,
                "research_family_id": r.research_family_id,
                "state_version": r.state_version,
                "active_lineage_count": sum(1 for l in lineages if l.status not in {"STOPPED", "COMPLETED_AFTER_SESSION_CANCELLATION"}),
                "pending_reviews": pending,
                "promising_candidate_count": promising,
                "experiments_count": len([l for l in lineages if l.best_artifact_id]),
                "budget_used": usage.model_dump(),
                "validation_exposures": usage.validation_exposures,
                "updated_at": (r.paused_at or r.started_at or r.created_at).isoformat()
                if (r.paused_at or r.started_at or r.created_at)
                else None,
            }
        )
    return {"items": items, "limit": limit, "offset": offset}


@router.get("/factor-discovery/mining/sessions/{session_id}")
def get_mining_session(session_id: str):
    _require_factor_discovery_mining()
    from services.factor_discovery.mining.session_detail_service import FactorMiningSessionDetailService

    return FactorMiningSessionDetailService().get_session_detail(session_id)


@router.get("/factor-discovery/mining/sessions/{session_id}/events")
def get_mining_events(session_id: str):
    _require_factor_discovery_mining()
    from services.factor_discovery.mining.repositories import FactorMiningEventRepository

    rows = FactorMiningEventRepository().list_for_session(session_id)
    return {
        "items": [
            {
                "event_id": e.event_id,
                "event_type": e.event_type,
                "previous_state": e.previous_state,
                "new_state": e.new_state,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in rows
        ]
    }


@router.get("/factor-discovery/mining/sessions/{session_id}/summary")
def get_mining_summary(session_id: str):
    _require_factor_discovery_mining()
    from services.factor_discovery.mining.summary_service import FactorMiningSummaryService

    return FactorMiningSummaryService().build_summary(session_id).model_dump(mode="json")


def _require_factor_discovery_read():
    _require_research_api()
    from config import FACTOR_DISCOVERY_ENABLED

    if not FACTOR_DISCOVERY_ENABLED:
        raise HTTPException(status_code=503, detail="FACTOR_DISCOVERY_ENABLED is false")


# --- Factor Discovery Phase 9A: candidate review & evidence ---


@router.get("/factor-discovery/candidates/hypotheses/{candidate_id}")
def get_hypothesis_candidate_detail(candidate_id: str):
    _require_factor_discovery_read()
    from services.factor_discovery.candidate_detail_service import FactorCandidateDetailService
    from services.factor_discovery.errors import FactorDiscoveryError

    try:
        return FactorCandidateDetailService().get_hypothesis_detail(candidate_id)
    except FactorDiscoveryError as exc:
        raise HTTPException(status_code=404, detail={"code": exc.code, "message": exc.message}) from exc


@router.get("/factor-discovery/candidates/formulas/{candidate_id}")
def get_formula_candidate_detail(candidate_id: str):
    _require_factor_discovery_read()
    from services.factor_discovery.candidate_detail_service import FactorCandidateDetailService
    from services.factor_discovery.errors import FactorDiscoveryError

    try:
        return FactorCandidateDetailService().get_formula_detail(candidate_id)
    except FactorDiscoveryError as exc:
        raise HTTPException(status_code=404, detail={"code": exc.code, "message": exc.message}) from exc


@router.get("/factor-discovery/candidates/revisions/{candidate_id}")
def get_revision_candidate_detail(candidate_id: str):
    _require_factor_discovery_read()
    from services.factor_discovery.candidate_detail_service import FactorCandidateDetailService
    from services.factor_discovery.errors import FactorDiscoveryError

    try:
        return FactorCandidateDetailService().get_revision_detail(candidate_id)
    except FactorDiscoveryError as exc:
        raise HTTPException(status_code=404, detail={"code": exc.code, "message": exc.message}) from exc


@router.get("/factor-discovery/mining/review-queue")
def get_mining_review_queue(
    review_type: str | None = Query(default=None),
    session_id: str | None = Query(default=None),
    research_family_id: str | None = Query(default=None),
    promising_only: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    _require_factor_discovery_mining()
    from services.factor_discovery.review_queue_service import FactorReviewQueueService

    return FactorReviewQueueService().list_queue(
        review_type=review_type,
        session_id=session_id,
        research_family_id=research_family_id,
        promising_only=promising_only,
        limit=limit,
        offset=offset,
    )


@router.get("/factor-discovery/mining/sessions/{session_id}/integrity")
def get_mining_session_integrity(session_id: str):
    _require_factor_discovery_mining()
    from services.factor_discovery.mining.errors import MiningIntegrityError
    from services.factor_discovery.mining.integrity_service import MiningIntegrityService

    try:
        return MiningIntegrityService().verify_mining_session_integrity(session_id)
    except MiningIntegrityError as exc:
        raise HTTPException(status_code=409, detail={"code": exc.code, "message": exc.message}) from exc


@router.get("/factor-discovery/factors")
def list_factor_registry(
    search: str | None = Query(default=None),
    lifecycle_status: str | None = Query(default=None),
    direction: str | None = Query(default=None),
    promising_only: bool = Query(default=False),
    has_validation: bool | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    _require_factor_discovery_read()
    from services.factor_discovery.factor_registry_service import FactorRegistryService

    return FactorRegistryService().list_factors(
        search=search,
        lifecycle_status=lifecycle_status,
        direction=direction,
        promising_only=promising_only,
        has_validation=has_validation,
        limit=limit,
        offset=offset,
    )


@router.get("/factor-discovery/factors/{factor_id}")
def get_factor_registry_detail(factor_id: str):
    _require_factor_discovery_read()
    from services.factor_discovery.errors import FactorDiscoveryError
    from services.factor_discovery.factor_registry_service import FactorRegistryService

    try:
        return FactorRegistryService().get_factor_detail(factor_id)
    except FactorDiscoveryError as exc:
        raise HTTPException(status_code=404, detail={"code": exc.code, "message": exc.message}) from exc


@router.get("/factor-discovery/factors/{factor_id}/versions/{version}")
def get_factor_registry_version(factor_id: str, version: str):
    _require_factor_discovery_read()
    from services.factor_discovery.errors import FactorDiscoveryError
    from services.factor_discovery.factor_registry_service import FactorRegistryService

    try:
        return FactorRegistryService().get_factor_version(factor_id, version)
    except FactorDiscoveryError as exc:
        raise HTTPException(status_code=404, detail={"code": exc.code, "message": exc.message}) from exc


@router.get("/factor-discovery/artifacts/{artifact_id}/validation-result")
def get_validation_result_by_artifact(artifact_id: str):
    _require_factor_discovery_read()
    from services.factor_discovery.errors import FactorDiscoveryError
    from services.factor_discovery.validation_result_service import FactorValidationResultService

    try:
        return FactorValidationResultService().get_by_artifact_id(artifact_id)
    except FactorDiscoveryError as exc:
        raise HTTPException(status_code=404, detail={"code": exc.code, "message": exc.message}) from exc


@router.get("/factor-discovery/runs/{run_id}/validation-result")
def get_validation_result_by_run(run_id: str):
    _require_factor_discovery_read()
    from services.factor_discovery.errors import FactorDiscoveryError
    from services.factor_discovery.validation_result_service import FactorValidationResultService

    try:
        return FactorValidationResultService().get_by_run_id(run_id)
    except FactorDiscoveryError as exc:
        raise HTTPException(status_code=404, detail={"code": exc.code, "message": exc.message}) from exc
