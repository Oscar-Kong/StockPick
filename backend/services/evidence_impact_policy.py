"""Centralized evidence impact policy — no scattered score mutations."""
from __future__ import annotations

from typing import Any

from config import RESEARCH_MAX_ORDINARY_MODIFIER
from models.schemas_research import EvidenceImpact, EvidenceImpactEvaluation

MAJOR_IMPACTS: frozenset[EvidenceImpact] = frozenset({"major_positive", "major_negative", "integrity_blocker"})
ORDINARY_IMPACTS: frozenset[EvidenceImpact] = frozenset({"supporting", "contradicting"})


def default_impact_for_run_type(run_type: str) -> EvidenceImpact:
    """Research runs default to informational unless gate upgrades them."""
    if run_type in ("quant_job",):
        return "informational"
    return "informational"


def evaluate_evidence_impact(
    *,
    proposed_impact: EvidenceImpact,
    gate_review_required: bool = False,
    integrity_blocked: bool = False,
) -> EvidenceImpactEvaluation:
    """Classify impact and compute capped ordinary modifier (display-only by default)."""
    impact: EvidenceImpact = proposed_impact
    codes: list[str] = []

    if integrity_blocked:
        impact = "integrity_blocker"
        codes.append("integrity_blocker_forced")

    review_required = gate_review_required or impact in MAJOR_IMPACTS
    max_mod = max(0.0, float(RESEARCH_MAX_ORDINARY_MODIFIER))
    display_only = max_mod <= 0.0

    modifier = 0.0
    if impact == "supporting" and not display_only:
        modifier = max_mod
        codes.append("supporting_modifier_applied")
    elif impact == "contradicting" and not display_only:
        modifier = -max_mod
        codes.append("contradicting_modifier_applied")
    elif impact in MAJOR_IMPACTS:
        modifier = 0.0
        codes.append("major_impact_display_only_until_review")
    else:
        codes.append("informational_no_modifier")

    return EvidenceImpactEvaluation(
        impact_level=impact,
        score_modifier=modifier,
        display_only=display_only or impact not in ORDINARY_IMPACTS,
        explanation_codes=codes,
        review_required=review_required,
    )


def apply_ordinary_modifier_to_score(base_score: float, evaluation: EvidenceImpactEvaluation) -> float:
    """Apply capped modifier only when policy allows — never for major/integrity impacts."""
    if evaluation.display_only or evaluation.impact_level in MAJOR_IMPACTS:
        return base_score
    return base_score + evaluation.score_modifier


def impact_from_gate_result(
    *,
    passed_major: bool,
    positive_direction: bool,
    integrity_blocked: bool,
) -> EvidenceImpact:
    if integrity_blocked:
        return "integrity_blocker"
    if passed_major:
        return "major_positive" if positive_direction else "major_negative"
    return "informational"
