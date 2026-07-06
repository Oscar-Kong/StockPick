"""Historical-store provider activation gate for staging."""
from __future__ import annotations

import config as app_config
from services.factor_discovery.errors import FactorDiscoveryError
from services.factor_discovery.staging.price_audit import FactorDiscoveryPriceAuditService
from services.factor_discovery.staging.universe_audit import FactorDiscoveryUniverseAuditService


def require_historical_store_for_staging() -> None:
    provider = app_config.FACTOR_RESEARCH_DATA_PROVIDER
    if provider != "historical_store":
        raise FactorDiscoveryError(
            "FACTOR_RESEARCH_DATA_PROVIDER_NOT_HISTORICAL_STORE",
            f"expected historical_store, got {provider}",
        )
    staging_enabled = bool(getattr(app_config, "FACTOR_DISCOVERY_STAGING_ENABLED", False))
    app_env = getattr(app_config, "APP_ENV", "development")
    if not staging_enabled and app_env not in ("test",):
        raise FactorDiscoveryError(
            "STAGING_PROVIDER_BLOCKED",
            "historical_store requires FACTOR_DISCOVERY_STAGING_ENABLED=true outside tests",
        )


def provider_readiness_blockers() -> list[str]:
    blockers: list[str] = []
    if app_config.FACTOR_RESEARCH_DATA_PROVIDER == "disabled":
        blockers.append("data_provider_disabled")
        return blockers
    if app_config.FACTOR_RESEARCH_DATA_PROVIDER != "historical_store":
        blockers.append(f"unsupported_provider:{app_config.FACTOR_RESEARCH_DATA_PROVIDER}")
        return blockers
    if not bool(getattr(app_config, "FACTOR_DISCOVERY_STAGING_ENABLED", False)):
        app_env = getattr(app_config, "APP_ENV", "development")
        if app_env not in ("test",):
            blockers.append("staging_not_enabled_for_historical_store")
    price = FactorDiscoveryPriceAuditService().audit()
    blockers.extend(price.blocking_codes)
    universe = FactorDiscoveryUniverseAuditService().audit()
    blockers.extend(universe.blocking_codes)
    return list(dict.fromkeys(blockers))
