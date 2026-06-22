"""Centralized research evidence consumption — bounded, auditable, no silent production changes."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from config import RESEARCH_MAX_ORDINARY_MODIFIER
from engines.audit.logger import audit_log
from models.schemas_research import EvidenceImpact, EvidenceImpactEvaluation
from services.evidence_impact_policy import apply_ordinary_modifier_to_score, evaluate_evidence_impact

logger = logging.getLogger(__name__)

REVIEW_IMPACTS: frozenset[str] = frozenset(
    {"supporting", "contradicting", "major_positive", "major_negative", "integrity_blocker"}
)


@dataclass
class ResearchEvidenceConsumption:
    base_score: float
    adjusted_score: float
    score_modifier: float = 0.0
    impact_level: EvidenceImpact = "informational"
    display_only: bool = True
    integrity_active: bool = False
    integrity_reasons: list[str] = field(default_factory=list)
    approved_staging_only: bool = True
    explanation_codes: list[str] = field(default_factory=list)


def _lookup_symbol_evidence(symbol: str, sleeve: str) -> tuple[EvidenceImpact, list[str], list[str]]:
    """Best-effort lookup of active research evidence for a symbol."""
    impacts: list[str] = []
    warnings: list[str] = []
    run_ids: list[str] = []
    try:
        from services.evidence_memory_service import list_evidence_memory

        mem = list_evidence_memory(symbol=symbol, limit=20)
        for item in mem.items:
            if item.evidence_impact in REVIEW_IMPACTS:
                impacts.append(item.evidence_impact)
            if item.evidence_impact == "integrity_blocker":
                warnings.append(item.deterministic_finding or "integrity_blocker")
            if item.run_id:
                run_ids.append(item.run_id)
    except Exception as exc:
        logger.debug("evidence memory lookup skipped: %s", exc)

    try:
        from data.db_engine import get_engine
        from engines.quant_models import ResearchRunIndex
        from sqlalchemy.orm import Session

        with Session(get_engine()) as session:
            rows = (
                session.query(ResearchRunIndex)
                .filter(
                    ResearchRunIndex.sleeve == sleeve,
                    ResearchRunIndex.evidence_impact.in_(tuple(REVIEW_IMPACTS)),
                    ResearchRunIndex.status == "completed",
                )
                .order_by(ResearchRunIndex.completed_at.desc())
                .limit(5)
                .all()
            )
            for row in rows:
                impacts.append(row.evidence_impact)
                if row.evidence_impact == "integrity_blocker":
                    warnings.extend(row.warnings or [])
                run_ids.append(row.run_id)
    except Exception as exc:
        logger.debug("run index lookup skipped: %s", exc)

    if "integrity_blocker" in impacts:
        return "integrity_blocker", warnings, run_ids
    if "major_positive" in impacts or "major_negative" in impacts:
        return impacts[0], warnings, run_ids  # major requires approved proposal — no score change
    if "supporting" in impacts:
        return "supporting", warnings, run_ids
    if "contradicting" in impacts:
        return "contradicting", warnings, run_ids
    return "informational", warnings, run_ids


def _approved_staging_proposal(run_ids: list[str]) -> bool:
    if not run_ids:
        return False
    try:
        from data.db_engine import get_engine
        from engines.quant_models import ChangeProposal
        from services.research_json import json_loads
        from sqlalchemy.orm import Session

        with Session(get_engine()) as session:
            rows = session.query(ChangeProposal).filter(ChangeProposal.status == "approved_for_staging").all()
            for row in rows:
                supported = json_loads(row.supporting_run_ids_json, [])
                if any(rid in supported for rid in run_ids):
                    return True
    except Exception:
        return False
    return False


def apply_research_evidence_to_score(
    base_score: float,
    *,
    symbol: str,
    sleeve: str,
    audit: bool = True,
) -> ResearchEvidenceConsumption:
    """Single bounded interface for score adjustment from research evidence."""
    impact_level, warnings, run_ids = _lookup_symbol_evidence(symbol, sleeve)
    has_major = impact_level in ("major_positive", "major_negative")
    approved = _approved_staging_proposal(run_ids)

    evaluation: EvidenceImpactEvaluation = evaluate_evidence_impact(
        proposed_impact=impact_level,  # type: ignore[arg-type]
        integrity_blocked=impact_level == "integrity_blocker",
        gate_review_required=has_major and not approved,
    )

    adjusted = base_score
    if has_major:
        evaluation = evaluate_evidence_impact(
            proposed_impact=impact_level,  # type: ignore[arg-type]
            gate_review_required=not approved,
        )
        adjusted = base_score
    else:
        adjusted = apply_ordinary_modifier_to_score(base_score, evaluation)

    consumption = ResearchEvidenceConsumption(
        base_score=base_score,
        adjusted_score=adjusted,
        score_modifier=round(adjusted - base_score, 4),
        impact_level=evaluation.impact_level,
        display_only=evaluation.display_only,
        integrity_active=impact_level == "integrity_blocker",
        integrity_reasons=warnings[:5],
        approved_staging_only=not approved,
        explanation_codes=evaluation.explanation_codes,
    )

    if audit:
        audit_log(
            "research_evidence_consumed",
            symbol=symbol,
            sleeve=sleeve,
            payload={
                "base_score": base_score,
                "adjusted_score": adjusted,
                "score_modifier": consumption.score_modifier,
                "impact_level": consumption.impact_level,
                "display_only": consumption.display_only,
                "integrity_active": consumption.integrity_active,
                "run_ids": run_ids[:10],
            },
        )
    return consumption


def apply_research_evidence_to_recommendation(
    recommendation: Any,
    *,
    symbol: str,
    sleeve: str,
    audit: bool = True,
) -> tuple[Any, list[str]]:
    """Integrity blockers may downgrade confidence — never upgrade from research alone."""
    if recommendation is None:
        return recommendation, []

    consumption = apply_research_evidence_to_score(
        float(getattr(recommendation, "confidence", 0) or 0),
        symbol=symbol,
        sleeve=sleeve,
        audit=False,
    )
    reasons: list[str] = []
    if not consumption.integrity_active:
        if audit:
            audit_log(
                "research_recommendation_boundary",
                symbol=symbol,
                sleeve=sleeve,
                payload={"action": "no_change", "impact_level": consumption.impact_level},
            )
        return recommendation, reasons

    conf = float(recommendation.confidence or 0)
    new_conf = max(0.0, min(100.0, conf * 0.85))
    recommendation.confidence = round(new_conf, 2)
    reasons = consumption.integrity_reasons or ["integrity_blocker_active"]
    strong_labels = {"strong_buy", "buy", "strong_sell", "sell"}
    if getattr(recommendation, "recommendation", "") in strong_labels:
        recommendation.recommendation = "watch"
        reasons.append("strong_label_prevented_by_integrity_blocker")

    if audit:
        audit_log(
            "research_recommendation_boundary",
            symbol=symbol,
            sleeve=sleeve,
            payload={
                "action": "downgraded",
                "confidence_before": conf,
                "confidence_after": new_conf,
                "reasons": reasons,
            },
        )
    return recommendation, reasons
