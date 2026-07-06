"""Operation budgets for Factor Discovery LLM calls."""
from __future__ import annotations

from datetime import datetime, timezone

import config as app_config
from data.db_engine import get_engine
from engines.factor_discovery_models import FactorLlmInteraction
from services.factor_discovery.llm.errors import FactorLlmBudgetExceededError
from services.factor_discovery.llm.models import LlmOperationType
from sqlalchemy.orm import Session


def enforce_candidate_limit(count: int, *, operation: str) -> None:
    if operation == "hypothesis" and count > app_config.FACTOR_DISCOVERY_LLM_MAX_HYPOTHESES:
        raise FactorLlmBudgetExceededError(
            "HYPOTHESIS_CANDIDATE_LIMIT", str(app_config.FACTOR_DISCOVERY_LLM_MAX_HYPOTHESES)
        )
    if operation == "formula" and count > app_config.FACTOR_DISCOVERY_LLM_MAX_FORMULAS:
        raise FactorLlmBudgetExceededError(
            "FORMULA_CANDIDATE_LIMIT", str(app_config.FACTOR_DISCOVERY_LLM_MAX_FORMULAS)
        )


def enforce_daily_family_budget(*, research_family_id: str, operation: LlmOperationType) -> None:
    if not research_family_id:
        return
    today = datetime.now(timezone.utc).replace(tzinfo=None).date()
    with Session(get_engine()) as session:
        rows = (
            session.query(FactorLlmInteraction)
            .filter(
                FactorLlmInteraction.research_family_id == research_family_id,
                FactorLlmInteraction.operation_type == operation.value,
            )
            .all()
        )
        count = sum(1 for r in rows if r.created_at and r.created_at.date() == today)
    if count >= app_config.FACTOR_DISCOVERY_LLM_DAILY_CALLS_PER_FAMILY:
        raise FactorLlmBudgetExceededError("DAILY_FAMILY_BUDGET_EXCEEDED", research_family_id)
