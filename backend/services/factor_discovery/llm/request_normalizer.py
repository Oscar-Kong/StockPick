"""Research request normalization for Factor Discovery LLM."""
from __future__ import annotations

from config import FACTOR_DISCOVERY_LLM_MAX_HYPOTHESES
from services.factor_discovery.llm.models import FactorResearchRequest, NormalizedFactorResearchRequest
from services.factor_discovery.repositories import FactorResearchFamilyRepository


def normalize_research_request(
    req: FactorResearchRequest,
    *,
    research_family_id: str,
) -> NormalizedFactorResearchRequest:
    family = FactorResearchFamilyRepository().get(research_family_id)
    if family is None:
        raise ValueError(f"research family not found: {research_family_id}")
    count = min(req.candidate_count, FACTOR_DISCOVERY_LLM_MAX_HYPOTHESES)
    horizon = req.holding_period_sessions or family.primary_horizon_sessions
    horizon = max(1, min(504, horizon))
    return NormalizedFactorResearchRequest(
        research_objective=req.research_objective.strip()[:4000],
        intended_universe=req.intended_universe or family.intended_universe,
        holding_period_sessions=horizon,
        rebalance_frequency=req.rebalance_frequency or "monthly",
        candidate_count=count,
        required_data_classes=[dc.value for dc in req.required_data_classes] or ["price"],
        primary_horizon_sessions=family.primary_horizon_sessions,
        validation_config_family_id=family.validation_config_family_id,
    )
