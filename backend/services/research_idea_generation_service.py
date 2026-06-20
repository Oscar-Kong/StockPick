"""Deterministic idea generation from research brief findings."""
from __future__ import annotations

import re
from typing import Any

from buckets import DEFAULT_BUCKET
from models.schemas_research import (
    GenerateIdeasResponse,
    ResearchBriefFinding,
    ResearchIdeaCreate,
    ResearchIdeaResponse,
)
from services.research_brief_service import build_research_brief
from services.research_ideas_service import create_idea, list_ideas

OPEN_STATUSES = frozenset({"new", "saved", "ready_to_test", "running"})


def _normalize_key(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip())[:120]


def _idea_dedup_key(finding: ResearchBriefFinding) -> str:
    return _normalize_key(f"{finding.finding_id}:{finding.title}")


def _existing_dedup_keys(sleeve: str | None) -> set[str]:
    keys: set[str] = set()
    listed = list_ideas(sleeve=sleeve, limit=200)
    for idea in listed.ideas:
        if idea.status not in OPEN_STATUSES:
            continue
        keys.add(_normalize_key(f"{idea.source_type}:{idea.title}"))
        for ref in idea.source_references:
            keys.add(_normalize_key(ref))
    return keys


def _source_type_for_finding(finding: ResearchBriefFinding) -> str:
    if "deteriorat" in finding.title.lower() or "error" in finding.title.lower():
        return "factor_deterioration" if "factor" in finding.title.lower() else "prediction_drift"
    if finding.evidence_impact == "integrity_blocker":
        return "data_quality"
    if finding.suggested_experiment_type == "pairs_discovery":
        return "pair_relationship"
    if finding.suggested_experiment_type == "walk_forward":
        return "failed_experiment" if "few" in finding.title.lower() else "factor_improvement"
    if finding.suggested_experiment_type == "prediction_calibration":
        return "prediction_drift"
    return "factor_deterioration"


def finding_to_idea_create(finding: ResearchBriefFinding, *, sleeve: str | None) -> ResearchIdeaCreate:
    params = dict(finding.suggested_parameters)
    if sleeve and "sleeve" not in params:
        params["sleeve"] = sleeve
    return ResearchIdeaCreate(
        title=finding.title[:256],
        hypothesis=finding.explanation,
        description=finding.why_it_matters,
        why_now=finding.supporting_metric,
        source_type=_source_type_for_finding(finding),  # type: ignore[arg-type]
        source_references=[finding.source_reference, finding.finding_id],
        sleeve=sleeve or params.get("sleeve"),
        suggested_experiment_type=finding.suggested_experiment_type,
        suggested_parameters=params,
        priority=int(min(100, max(10, round(finding.confidence * 100)))),
        confidence=round(finding.confidence, 3),
        status="new",
        user_notes="",
    )


def generate_ideas_from_findings(
    findings: list[ResearchBriefFinding],
    *,
    sleeve: str | None = None,
    limit: int = 10,
) -> GenerateIdeasResponse:
    existing = _existing_dedup_keys(sleeve)
    created: list[ResearchIdeaResponse] = []
    skipped = 0

    for finding in findings[: limit * 2]:
        if len(created) >= limit:
            break
        key = _idea_dedup_key(finding)
        alt_key = _normalize_key(f"{_source_type_for_finding(finding)}:{finding.title}")
        if key in existing or alt_key in existing:
            skipped += 1
            continue
        idea = create_idea(finding_to_idea_create(finding, sleeve=sleeve))
        created.append(idea)
        existing.add(key)
        existing.add(alt_key)

    return GenerateIdeasResponse(
        created=created,
        skipped_duplicates=skipped,
        findings_used=len(findings),
    )


def duplicate_idea(idea_id: str) -> ResearchIdeaResponse | None:
    from services.research_ideas_service import get_idea

    src = get_idea(idea_id)
    if not src:
        return None
    return create_idea(
        ResearchIdeaCreate(
            title=f"{src.title} (copy)",
            hypothesis=src.hypothesis,
            description=src.description,
            why_now=src.why_now,
            source_type=src.source_type,
            source_references=list(src.source_references),
            sleeve=src.sleeve,
            universe_definition=dict(src.universe_definition),
            suggested_experiment_type=src.suggested_experiment_type,
            suggested_parameters=dict(src.suggested_parameters),
            priority=src.priority,
            confidence=src.confidence,
            status="saved",
            user_notes=src.user_notes,
        )
    )
