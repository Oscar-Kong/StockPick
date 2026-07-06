"""Consolidated UI readiness contract for Factor Discovery mining workspace."""
from __future__ import annotations

import config as app_config
from services.factor_discovery.historical_store_provider import assess_historical_store_capabilities
from services.factor_discovery.llm.capabilities import assess_llm_capabilities
from services.factor_discovery.mining.models import MiningSessionMode
from services.factor_discovery.mining.policies import require_mining_enabled
from services.factor_discovery.operations import factor_discovery_operational_status


def factor_discovery_mining_readiness(*, include_staging_preflight: bool = True) -> dict:
    ops = factor_discovery_operational_status()
    caps = assess_historical_store_capabilities()
    llm_caps = assess_llm_capabilities()

    discovery_enabled = bool(app_config.FACTOR_DISCOVERY_ENABLED)
    llm_enabled = bool(app_config.FACTOR_DISCOVERY_LLM_ENABLED)
    loop_enabled = bool(app_config.FACTOR_DISCOVERY_LOOP_ENABLED)
    loop_mode = app_config.FACTOR_DISCOVERY_LOOP_MODE

    supervised_ready = False
    bounded_auto_ready = False
    blocking: list[str] = []
    warnings: list[str] = list(llm_caps.warnings)

    if not discovery_enabled:
        blocking.append("FACTOR_DISCOVERY_ENABLED is false")
    if not loop_enabled:
        blocking.append("FACTOR_DISCOVERY_LOOP_ENABLED is false")
    if loop_mode not in {MiningSessionMode.SUPERVISED.value, MiningSessionMode.BOUNDED_AUTO.value}:
        blocking.append(f"FACTOR_DISCOVERY_LOOP_MODE={loop_mode} is not active")

    try:
        require_mining_enabled()
        if discovery_enabled and llm_enabled and not llm_caps.blocking_reasons:
            supervised_ready = loop_mode == MiningSessionMode.SUPERVISED.value
        if loop_mode == MiningSessionMode.BOUNDED_AUTO.value:
            # Bounded-auto remains partial — never expose as production-ready in Phase 8B.
            bounded_auto_ready = False
            warnings.append("Bounded auto mode is not yet available in the workspace")
    except Exception as exc:
        blocking.append(str(getattr(exc, "message", exc)))

    blocking.extend(llm_caps.blocking_reasons)
    if caps.blocking_reasons and app_config.FACTOR_RESEARCH_DATA_PROVIDER == "historical_store":
        blocking.extend(caps.blocking_reasons)

    snapshot_ready = ops.get("schema_ready", True)
    pit_ready = caps.pit_universe_available
    adjusted_ready = caps.adjusted_prices_available
    historical_ready = caps.price_research_available

    return {
        "factor_discovery_enabled": discovery_enabled,
        "factor_discovery_llm_enabled": llm_enabled,
        "mining_loop_enabled": loop_enabled,
        "current_mining_mode": loop_mode if loop_enabled else "disabled",
        "supervised_ready": supervised_ready and not blocking,
        "bounded_auto_ready": bounded_auto_ready,
        "llm_provider_ready": llm_caps.structured_json_available and not llm_caps.blocking_reasons,
        "llm_provider": llm_caps.provider_configured,
        "llm_model": getattr(llm_caps, "model_id", None),
        "data_provider_ready": caps.price_research_available and not caps.blocking_reasons,
        "data_provider": app_config.FACTOR_RESEARCH_DATA_PROVIDER,
        "snapshot_ready": snapshot_ready,
        "pit_universe_ready": pit_ready,
        "adjusted_prices_ready": adjusted_ready,
        "historical_store_ready": historical_ready,
        "pit_fundamentals_ready": caps.pit_fundamentals_available,
        "sector_history_ready": caps.pit_sector_history_available,
        "industry_history_ready": caps.pit_sector_history_available,
        "market_cap_history_ready": caps.historical_market_cap_available,
        "supported_fields": list(caps.supported_fields),
        "supported_field_groups": _field_groups(caps.supported_fields),
        "blocking_reasons": blocking,
        "warnings": warnings,
        "no_sealed_access": True,
        "no_production_integration": True,
        "infrastructure": {
            "schema_ready": ops.get("schema_ready", True),
            "active_mining_sessions": ops.get("active_mining_session_count", 0),
            "paused_mining_sessions": ops.get("paused_mining_session_count", 0),
            "active_worker_leases": ops.get("active_worker_lease_count", 0),
            "pending_sealed_receipts": ops.get("pending_sealed_receipt_count", 0),
            "failed_artifacts": ops.get("failed_sealed_receipt_count", 0),
        },
        "budget_defaults": {
            "max_formulas_reaching_evaluation": app_config.FACTOR_DISCOVERY_LOOP_DEFAULT_MAX_EVALUATED_FORMULAS,
            "max_revision_rounds_per_lineage": app_config.FACTOR_DISCOVERY_LOOP_DEFAULT_MAX_REVISION_ROUNDS,
            "max_validation_exposures_per_lineage": app_config.FACTOR_DISCOVERY_LOOP_DEFAULT_MAX_VALIDATION_EXPOSURES,
        },
        "staging_research_readiness": (
            _staging_research_readiness() if include_staging_preflight else _staging_research_readiness_skipped()
        ),
    }


def _staging_research_readiness_skipped() -> dict:
    return {
        "label": "Staging research readiness",
        "not_trading_readiness": True,
        "staging_enabled": bool(getattr(app_config, "FACTOR_DISCOVERY_STAGING_ENABLED", False)),
        "skipped": True,
        "limitations": ["Omitted during staging preflight to avoid recursive readiness evaluation"],
    }


def _staging_research_readiness() -> dict:
    try:
        from services.factor_discovery.staging.audit_artifact import FactorDiscoveryStagingAuditArtifact
        from services.factor_discovery.staging.price_audit import FactorDiscoveryPriceAuditService
        from services.factor_discovery.staging.universe_audit import FactorDiscoveryUniverseAuditService
        from services.factor_discovery.staging.provider_gate import provider_readiness_blockers

        price = FactorDiscoveryPriceAuditService().audit()
        universe = FactorDiscoveryUniverseAuditService().audit()
        blocking = list(dict.fromkeys(price.blocking_codes + universe.blocking_codes + provider_readiness_blockers()))
        latest = FactorDiscoveryStagingAuditArtifact().latest()
        return {
            "label": "Staging research readiness",
            "not_trading_readiness": True,
            "staging_enabled": bool(getattr(app_config, "FACTOR_DISCOVERY_STAGING_ENABLED", False)),
            "blocking_reasons": blocking,
            "price_coverage": price.to_dict(),
            "universe_coverage": universe.to_dict(),
            "latest_audit_status": (latest or {}).get("acceptance", {}).get("status"),
            "limitations": [
                "Passing staging readiness does not authorize production Scan or trading",
                "Sealed test remains unopened",
            ],
        }
    except Exception as exc:
        return {
            "label": "Staging research readiness",
            "not_trading_readiness": True,
            "staging_enabled": False,
            "blocking_reasons": [f"staging_preflight_unavailable:{exc}"],
            "limitations": [],
        }


def _field_groups(supported: tuple[str, ...] | list[str]) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {
        "price": [],
        "return": [],
        "volume": [],
        "volatility": [],
        "liquidity": [],
        "fundamental": [],
        "classification": [],
        "exposure": [],
    }
    for field in supported:
        lower = field.lower()
        if "close" in lower or "open" in lower or "high" in lower or "low" in lower or "price" in lower:
            groups["price"].append(field)
        elif "return" in lower or "ret" in lower:
            groups["return"].append(field)
        elif "volume" in lower:
            groups["volume"].append(field)
        elif "vol" in lower:
            groups["volatility"].append(field)
        elif "liquidity" in lower or "turnover" in lower:
            groups["liquidity"].append(field)
        elif any(k in lower for k in ("pe", "pb", "fundamental", "earnings", "revenue")):
            groups["fundamental"].append(field)
        elif any(k in lower for k in ("sector", "industry", "gics")):
            groups["classification"].append(field)
        else:
            groups["exposure"].append(field)
    return groups
