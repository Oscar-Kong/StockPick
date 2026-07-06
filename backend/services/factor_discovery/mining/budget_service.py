"""Budget enforcement for mining sessions."""
from __future__ import annotations

from services.factor_discovery.mining.errors import MiningBudgetExceededError
from services.factor_discovery.mining.models import FactorMiningBudgetPolicy, SessionUsageCounters


def load_usage(raw: str | None) -> SessionUsageCounters:
    if not raw:
        return SessionUsageCounters()
    import json

    try:
        data = json.loads(raw)
        return SessionUsageCounters.model_validate(data)
    except Exception:
        return SessionUsageCounters()


def check_budget(
    policy: FactorMiningBudgetPolicy,
    usage: SessionUsageCounters,
    *,
    operation: str,
    amount: int = 1,
) -> None:
    checks = {
        "hypothesis_generation": ("max_hypothesis_generation_calls", usage.hypothesis_generation_calls),
        "hypothesis": ("max_hypotheses", usage.hypotheses_generated),
        "hypothesis_approved": ("max_hypotheses_approved_for_translation", usage.hypotheses_approved),
        "formula": ("max_total_formula_candidates", usage.formulas_generated),
        "evaluation": ("max_formulas_reaching_evaluation", usage.formulas_evaluated),
        "revision": ("max_total_revision_attempts", usage.revision_rounds),
        "llm": ("max_llm_interactions", usage.llm_interactions),
        "failure": ("max_failed_attempts", usage.failed_attempts),
        "exposure": ("max_validation_exposures_per_lineage", usage.validation_exposures),
    }
    if operation not in checks:
        return
    field, current = checks[operation]
    limit = getattr(policy, field)
    if current + amount > limit:
        raise MiningBudgetExceededError("MINING_BUDGET_EXCEEDED", f"{operation}:{current + amount}>{limit}")


def reserve_usage(usage: SessionUsageCounters, operation: str, *, tokens: int = 0) -> SessionUsageCounters:
    data = usage.model_dump()
    mapping = {
        "hypothesis_generation": "hypothesis_generation_calls",
        "hypothesis": "hypotheses_generated",
        "hypothesis_approved": "hypotheses_approved",
        "formula": "formulas_generated",
        "evaluation": "formulas_evaluated",
        "revision": "revision_rounds",
        "llm": "llm_interactions",
        "failure": "failed_attempts",
        "exposure": "validation_exposures",
        "duplicate": "duplicates_prevented",
    }
    key = mapping.get(operation)
    if key:
        data[key] = data.get(key, 0) + 1
    if tokens:
        data["total_tokens"] = data.get("total_tokens", 0) + tokens
        data["llm_interactions"] = data.get("llm_interactions", 0) + 1
    return SessionUsageCounters.model_validate(data)
