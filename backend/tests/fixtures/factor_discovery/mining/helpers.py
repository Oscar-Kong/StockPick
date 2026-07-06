"""Shared helpers for Factor Discovery mining tests."""
from __future__ import annotations

import config
from engines.factor.discovery.validation_models import FactorValidationConfig
from engines.quant_db import init_quant_db
from models.schemas_factor_discovery import DiscoveryPeriodSplit
from services.factor_discovery.llm.client import FixtureLlmClient, clear_fixture_responses
from services.factor_discovery.mining.models import (
    FactorMiningAutoPolicy,
    FactorMiningBudgetPolicy,
    FactorMiningSessionCreateRequest,
    MiningSessionMode,
)
from services.factor_discovery.repositories import FactorResearchFamilyRepository
from tests.fixtures.factor_discovery.llm.helpers import register_hypothesis_fixture, sample_research_request
from tests.fixtures.factor_discovery.validation.validation_panel_builder import build_validation_context


def enable_mining(monkeypatch) -> FixtureLlmClient:
    from tests.fixtures.factor_discovery.llm.helpers import enable_llm_fixture

    monkeypatch.setenv("FACTOR_DISCOVERY_LOOP_ENABLED", "true")
    monkeypatch.setenv("FACTOR_DISCOVERY_ENABLED", "true")
    config.FACTOR_DISCOVERY_LOOP_ENABLED.set(True)
    config.FACTOR_DISCOVERY_ENABLED.set(True)
    monkeypatch.setattr(config, "FACTOR_DISCOVERY_LOOP_MODE", "supervised", raising=False)
    client = enable_llm_fixture(monkeypatch)
    return client


def mining_session_request(**overrides) -> FactorMiningSessionCreateRequest:
    ctx = build_validation_context()
    family_id = FactorResearchFamilyRepository().create(
        research_objective="mining test",
        intended_universe="research",
        primary_horizon_sessions=ctx["validation_config"].primary_horizon_sessions,
        data_source_policy_id="research_adjusted_daily_v1",
        validation_config_family_id="default_v1",
        created_by="test",
    )
    base = dict(
        research_family_id=family_id,
        research_request=sample_research_request(candidate_count=1),
        session_mode=MiningSessionMode.SUPERVISED,
        period_split=ctx["period_split"],
        validation_config=ctx["validation_config"],
        data_provider_id="fixture",
        budget_policy=FactorMiningBudgetPolicy(
            max_hypothesis_generation_calls=2,
            max_hypotheses=2,
            max_formulas_reaching_evaluation=3,
            max_revision_rounds_per_lineage=1,
        ),
        auto_policy=FactorMiningAutoPolicy(),
        actor="tester",
    )
    base.update(overrides)
    return FactorMiningSessionCreateRequest(**base)


def authorize_and_start(session_svc, session_id: str, *, actor: str = "tester") -> int:
    session_svc.authorize_session(session_id, actor=actor, reason="test authorization", state_version=0)
    out = session_svc.start_session(session_id, actor=actor, state_version=1)
    return out["state_version"]
