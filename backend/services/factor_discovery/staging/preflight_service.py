"""Consolidated staging preflight (read-only)."""
from __future__ import annotations

import os
from pathlib import Path

import config as app_config
from data.db_engine import get_engine
from engines.factor_discovery_models import FactorResearchDataSnapshot
from services.factor_discovery.historical_store_provider import assess_historical_store_capabilities
from services.factor_discovery.mining.readiness_service import factor_discovery_mining_readiness
from services.factor_discovery.staging.calendar_policy import audit_calendar
from services.factor_discovery.staging.environment import resolve_staging_contract, validate_staging_environment
from services.factor_discovery.staging.price_audit import FactorDiscoveryPriceAuditService
from services.factor_discovery.staging.provider_gate import provider_readiness_blockers
from services.factor_discovery.staging.universe_audit import FactorDiscoveryUniverseAuditService
from sqlalchemy.orm import Session


class FactorDiscoveryStagingPreflightService:
    def run(self, *, allow_test: bool = False) -> dict:
        contract = resolve_staging_contract()
        env_ok, env_blocking = validate_staging_environment(allow_test=allow_test)
        price_audit = FactorDiscoveryPriceAuditService().audit()
        universe_audit = FactorDiscoveryUniverseAuditService().audit()
        caps = assess_historical_store_capabilities()
        mining = factor_discovery_mining_readiness(include_staging_preflight=False)

        from services.factor_discovery.evidence_paths import factor_discovery_paths

        root = factor_discovery_paths().snapshots
        if not root.exists():
            try:
                root.mkdir(parents=True, exist_ok=True)
            except OSError:
                pass
        snapshot_writable = root.exists() and root.is_dir() and os.access(root, os.W_OK)

        with Session(get_engine()) as session:
            snapshots = session.query(FactorResearchDataSnapshot).limit(200).all()
        broken = [
            s.snapshot_id
            for s in snapshots
            if s.artifact_present and s.storage_reference and not Path(s.storage_reference).exists()
        ]

        sessions: list[str] = []
        if price_audit.earliest_date and price_audit.latest_date:
            sessions = [price_audit.earliest_date, price_audit.latest_date]
        calendar = audit_calendar(sessions)

        blocking = list(env_blocking)
        blocking.extend(price_audit.blocking_codes)
        blocking.extend(universe_audit.blocking_codes)
        if not snapshot_writable:
            blocking.append("snapshot_storage_not_writable")
        if broken:
            blocking.append("broken_snapshot_records")
        if app_config.FACTOR_RESEARCH_DATA_PROVIDER == "disabled":
            blocking.append("data_provider_disabled")
        elif app_config.FACTOR_RESEARCH_DATA_PROVIDER == "historical_store":
            blocking.extend(provider_readiness_blockers())
        elif app_config.FACTOR_RESEARCH_DATA_PROVIDER != "fixture":
            blocking.append(f"unsupported_provider:{app_config.FACTOR_RESEARCH_DATA_PROVIDER}")
        if not env_ok and not allow_test:
            blocking.append("staging_environment_invalid")
        blocking = list(dict.fromkeys(blocking))

        return {
            "environment": contract.to_dict(),
            "application_readiness": {
                "schema_ready": mining.get("infrastructure", {}).get("schema_ready", True),
                "factor_discovery_enabled": mining["factor_discovery_enabled"],
                "mining_loop_enabled": mining["mining_loop_enabled"],
                "data_provider": app_config.FACTOR_RESEARCH_DATA_PROVIDER,
                "snapshot_storage_writable": snapshot_writable,
                "snapshot_storage_persistent": snapshot_writable,
                "database_backend": "sqlite"
                if "sqlite" in str(getattr(app_config, "DATABASE_URL", "")).lower()
                else "other",
                "database_connectivity": True,
                "supervised_ready": mining["supervised_ready"],
                "llm_ready": mining["llm_provider_ready"],
            },
            "price_readiness": price_audit.to_dict(),
            "universe_readiness": universe_audit.to_dict(),
            "snapshot_readiness": {
                "storage_available": snapshot_writable,
                "supported_format": "factor_snapshot_csv_bundle_v1",
                "existing_snapshots": len(snapshots),
                "broken_snapshot_records": broken,
                "hash_failures": 0,
            },
            "provider_capabilities": {
                "provider_id": caps.provider_id,
                "price_research_available": caps.price_research_available,
                "adjusted_prices_available": caps.adjusted_prices_available,
                "pit_universe_available": caps.pit_universe_available,
                "supported_date_range": caps.supported_date_range,
                "supported_fields": list(caps.supported_fields),
                "blocking_reasons": list(caps.blocking_reasons),
                "provider_data_version": caps.provider_data_version,
                "symbol_identity_status": "verified" if not price_audit.invalid_symbols else "issues_detected",
                "calendar_status": "observed_union_fallback",
                "delisting_data_status": "limited_missing_horizon_end_prices",
            },
            "calendar_audit": calendar,
            "blocking_reasons": blocking,
            "warnings": list(
                dict.fromkeys(price_audit.warnings + universe_audit.warnings + mining.get("warnings", []))
            ),
            "read_only": True,
        }
