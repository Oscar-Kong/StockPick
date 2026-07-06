"""Verify Quant Lab / factor discovery cannot silently mutate live production scoring."""
from __future__ import annotations

from config import FACTOR_MODEL_VERSION, STRATEGY_VERSION


def verify_research_isolation() -> dict:
    """Static audit of known write paths from research into production."""
    blockers: list[str] = []
    warnings: list[str] = []
    write_paths_blocked: list[str] = []
    write_paths_absent: list[str] = []

    # Production promotion execution path must NOT exist (Phase 10 is governance-only)
    try:
        import importlib

        importlib.import_module("engines.factor.discovery.scan_adapter")
        blockers.append("scan_adapter_exists:production_factor_hook_present")
    except ModuleNotFoundError:
        write_paths_absent.append("engines.factor.discovery.scan_adapter")

    try:
        importlib.import_module("services.factor_discovery_approval_service")
        blockers.append("approval_service_exists:automatic_production_promotion")
    except ModuleNotFoundError:
        write_paths_absent.append("services.factor_discovery_approval_service")

    from services.factor_discovery.lifecycle_service import FactorLifecycleService
    from services.factor_discovery.errors import ProductionPromotionError
    from models.schemas_factor_discovery import FactorLifecycleStatus
    from services.factor_discovery.lifecycle_service import LifecycleTransitionRequest

    try:
        FactorLifecycleService().transition(
            LifecycleTransitionRequest(
                factor_id="isolation_probe",
                factor_version="1.0.0",
                target_status=FactorLifecycleStatus.PRODUCTION,
                actor_type="system",
                actor_identifier="isolation_audit",
                reason="probe",
            )
        )
        blockers.append("lifecycle_production_transition_not_blocked")
    except ProductionPromotionError:
        write_paths_blocked.append("FactorLifecycleService.transition(PRODUCTION)")

    from services.factor_discovery.promotion.candidate_service import FactorPromotionCandidateService

    live = FactorPromotionCandidateService.verify_live_config_unchanged()
    if live.get("live_mutation"):
        blockers.append("live_config_mutation_flag")

    # Change proposals do not auto-apply
    from services.change_proposals_service import update_proposal  # noqa: F401

    warnings.append("change_proposals_require_separate_manual_integration")

    return {
        "blockers": blockers,
        "warnings": warnings,
        "write_paths_blocked": write_paths_blocked,
        "write_paths_absent": write_paths_absent,
        "factor_model_version": FACTOR_MODEL_VERSION,
        "strategy_version": STRATEGY_VERSION,
        "advisory_only": True,
    }
