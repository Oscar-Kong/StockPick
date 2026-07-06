"""Survivorship bias audit for staging datasets."""
from __future__ import annotations

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from data.db_engine import get_engine
from engines.quant_models import UniversePit
from services.factor_discovery.staging.audit_limits import MAXIMUM_FLAGGED_EXAMPLES_PER_CATEGORY
from services.factor_discovery.staging.universe_audit import FactorDiscoveryUniverseAuditService


class FactorDiscoverySurvivorshipAuditService:
    def audit(self) -> dict:
        universe = FactorDiscoveryUniverseAuditService().audit()
        historical_only: list[str] = []
        current_only: list[str] = []
        total_historical = universe.unique_symbols
        latest_date = universe.latest_date
        with Session(get_engine()) as session:
            if latest_date:
                latest_syms = {
                    r[0]
                    for r in session.execute(
                        text(
                            "SELECT symbol FROM universe_pit WHERE is_active = 1 AND as_of_date = :d"
                        ),
                        {"d": latest_date},
                    ).fetchall()
                }
                all_syms = {
                    r[0]
                    for r in session.execute(
                        text("SELECT DISTINCT symbol FROM universe_pit WHERE is_active = 1")
                    ).fetchall()
                }
                historical_only = sorted(all_syms - latest_syms)[:MAXIMUM_FLAGGED_EXAMPLES_PER_CATEGORY]
                current_only = sorted(latest_syms)[:MAXIMUM_FLAGGED_EXAMPLES_PER_CATEGORY]
            batch_count = session.execute(
                text("SELECT COUNT(*) FROM universe_pit WHERE bucket_hint LIKE 'staging:%'")
            ).scalar() or 0
            total_rows = session.query(func.count()).select_from(UniversePit).scalar() or 0
            verified_ratio = round(batch_count / max(total_rows, 1), 4)

        pct_still_current = 0.0
        if total_historical:
            pct_still_current = round(
                (len(current_only) / total_historical) if current_only else 0.0,
                4,
            )

        blocking = list(universe.blocking_codes)
        if universe.unique_dates < 2:
            blocking.append("insufficient_pit_date_coverage")
        if universe.current_list_only_pattern:
            blocking.append("current_list_backfill_detected")
        if universe.entry_events == 0 and universe.unique_dates > 30:
            blocking.append("no_entry_events")
        if universe.exit_events == 0 and universe.unique_dates > 30:
            blocking.append("no_exit_events")

        return {
            "eligible_symbols_by_session_available": universe.unique_dates > 0,
            "membership_counts_by_date": {
                "min": universe.min_eligible_per_date,
                "median": universe.median_eligible_per_date,
                "max": universe.max_eligible_per_date,
            },
            "entry_events": universe.entry_events,
            "exit_events": universe.exit_events,
            "total_unique_historical_members": total_historical,
            "total_current_members": len(current_only),
            "historical_only_members": historical_only,
            "current_only_members": current_only,
            "pct_historical_still_current": pct_still_current,
            "pct_verified_pit_provenance": verified_ratio,
            "constant_membership_ratio": universe.constant_membership_ratio,
            "current_list_only_pattern": universe.current_list_only_pattern,
            "current_list_backfill_detected": universe.current_list_only_pattern,
            "pit_evidence_status": universe.survivorship_status,
            "blocking_codes": list(dict.fromkeys(blocking)),
            "wording": _wording(universe.survivorship_status),
            "limitations": [
                "Delisting returns not imputed; missing terminal outcomes reported separately",
                "Staging curated source is not index-official membership",
            ],
        }


def _wording(status: str) -> str:
    mapping = {
        "pit_membership_verified": "PIT membership verified for the audited source and period",
        "pit_membership_partially_verified": "PIT membership partially verified for the audited source and period",
        "current_list_bias_detected": "Survivorship risk remains because membership appears constant across dates",
        "unverified": "Survivorship risk remains because provenance is unverified",
    }
    return mapping.get(status, "Survivorship risk remains because membership provenance is incomplete")
