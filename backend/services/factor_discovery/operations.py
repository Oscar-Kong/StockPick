"""Factor Discovery operational diagnostics."""
from __future__ import annotations

from data.db_engine import get_engine
from engines.factor_discovery_models import (
    FactorDiscoveryRun,
    FactorLlmInteraction,
    FactorSealedTestReceipt,
    FactorValidationArtifactRecord,
)
from config import (
    FACTOR_DISCOVERY_ENABLED,
    FACTOR_DISCOVERY_LLM_ENABLED,
    FACTOR_DISCOVERY_LOOP_ENABLED,
    FACTOR_DISCOVERY_LOOP_MODE,
    FACTOR_RESEARCH_DATA_PROVIDER,
)
from engines.factor_discovery_models import FactorMiningSession
from services.factor_discovery.mining.policies import require_mining_enabled
from services.factor_discovery.historical_store_provider import assess_historical_store_capabilities
from services.factor_discovery.llm.capabilities import assess_llm_capabilities
from sqlalchemy.orm import Session


def factor_discovery_operational_status() -> dict:
    caps = assess_historical_store_capabilities()
    llm_caps = assess_llm_capabilities()
    engine = get_engine()
    with Session(engine) as session:
        failed_runs = session.query(FactorDiscoveryRun).filter(FactorDiscoveryRun.status == "failed").count()
        pending_sealed = (
            session.query(FactorSealedTestReceipt).filter(FactorSealedTestReceipt.status == "RESERVED").count()
        )
        failed_sealed = (
            session.query(FactorSealedTestReceipt).filter(FactorSealedTestReceipt.status == "FAILED").count()
        )
        artifacts = session.query(FactorValidationArtifactRecord).count()
        llm_interactions = session.query(FactorLlmInteraction).count()
        failed_llm = session.query(FactorLlmInteraction).filter(FactorLlmInteraction.status == "FAILED").count()
        active_mining = session.query(FactorMiningSession).filter(
            FactorMiningSession.status.notin_(["COMPLETED", "CANCELLED", "BUDGET_EXHAUSTED", "FAILED"])
        ).count()
        paused_mining = session.query(FactorMiningSession).filter(FactorMiningSession.status == "PAUSED").count()
        awaiting_revision = session.query(FactorMiningSession).filter(
            FactorMiningSession.status == "AWAITING_REVISION_REVIEW"
        ).count()
        running_experiments = session.query(FactorMiningSession).filter(
            FactorMiningSession.status == "RUNNING_EXPERIMENTS"
        ).count()
        active_leases = session.query(FactorMiningSession).filter(FactorMiningSession.lease_token.isnot(None)).count()
    loop_ready = False
    loop_blocking: list[str] = []
    try:
        require_mining_enabled()
        loop_ready = True
    except Exception as exc:
        loop_blocking.append(str(getattr(exc, "message", exc)))
    return {
        "feature_flag_enabled": bool(FACTOR_DISCOVERY_ENABLED),
        "llm_feature_flag_enabled": bool(FACTOR_DISCOVERY_LLM_ENABLED),
        "loop_feature_flag_enabled": bool(FACTOR_DISCOVERY_LOOP_ENABLED),
        "loop_mode": FACTOR_DISCOVERY_LOOP_MODE,
        "loop_ready": loop_ready,
        "loop_blocking_reasons": loop_blocking,
        "selected_provider": FACTOR_RESEARCH_DATA_PROVIDER,
        "llm_provider": llm_caps.provider_configured,
        "llm_capabilities": {
            "structured_json_available": llm_caps.structured_json_available,
            "hypothesis_generation_supported": llm_caps.hypothesis_generation_supported,
            "dsl_translation_supported": llm_caps.dsl_translation_supported,
            "critique_supported": llm_caps.critique_supported,
            "run_interpretation_supported": llm_caps.run_interpretation_supported,
            "blocking_reasons": list(llm_caps.blocking_reasons),
            "warnings": list(llm_caps.warnings),
        },
        "provider_capabilities": {
            "price_research_available": caps.price_research_available,
            "adjusted_prices_available": caps.adjusted_prices_available,
            "pit_universe_available": caps.pit_universe_available,
            "pit_fundamentals_available": caps.pit_fundamentals_available,
            "pit_sector_history_available": caps.pit_sector_history_available,
            "historical_market_cap_available": caps.historical_market_cap_available,
            "supported_fields": list(caps.supported_fields),
            "blocking_reasons": list(caps.blocking_reasons),
            "supported_date_range": caps.supported_date_range,
        },
        "schema_ready": True,
        "failed_run_count": failed_runs,
        "pending_sealed_receipt_count": pending_sealed,
        "failed_sealed_receipt_count": failed_sealed,
        "validation_artifact_count": artifacts,
        "llm_interaction_count": llm_interactions,
        "failed_llm_interaction_count": failed_llm,
        "active_mining_session_count": active_mining,
        "paused_mining_session_count": paused_mining,
        "awaiting_revision_review_count": awaiting_revision,
        "running_experiments_session_count": running_experiments,
        "active_worker_lease_count": active_leases,
        "no_sealed_access": True,
        "no_production_scan_integration": True,
    }
