"""Session integrity verification for mining workflows."""
from __future__ import annotations

from services.factor_discovery.mining.budget_service import load_usage
from services.factor_discovery.mining.errors import MiningIntegrityError
from services.factor_discovery.mining.hashing import event_log_hash
from services.factor_discovery.mining.repositories import (
    FactorMiningEvaluationRepository,
    FactorMiningEventRepository,
    FactorMiningExposureRepository,
    FactorMiningLineageRepository,
    FactorMiningSessionRepository,
)
from services.research_json import json_loads


class MiningIntegrityService:
    def __init__(self) -> None:
        self._sessions = FactorMiningSessionRepository()
        self._events = FactorMiningEventRepository()
        self._lineages = FactorMiningLineageRepository()
        self._evaluations = FactorMiningEvaluationRepository()
        self._exposures = FactorMiningExposureRepository()

    def verify_mining_session_integrity(self, session_id: str) -> dict:
        row = self._sessions.get(session_id)
        if row is None:
            raise MiningIntegrityError("SESSION_NOT_FOUND", session_id)
        events = self._events.list_for_session(session_id)
        computed = event_log_hash(
            [
                {
                    "event_type": e.event_type,
                    "previous_state": e.previous_state,
                    "new_state": e.new_state,
                    "reason_code": e.reason_code,
                    "lineage_id": e.lineage_id,
                    "candidate_id": e.candidate_id,
                    "run_id": e.run_id,
                }
                for e in events
            ]
        )
        if row.summary_hash and row.summary_json:
            summary = json_loads(row.summary_json, {})
            if summary.get("event_log_hash") and summary["event_log_hash"] != computed:
                raise MiningIntegrityError("EVENT_LOG_HASH_MISMATCH", computed)
        usage = load_usage(row.usage_json)
        exposure_count = self._exposures.count_for_session(session_id)
        if usage.validation_exposures != exposure_count:
            raise MiningIntegrityError(
                "EXPOSURE_COUNT_MISMATCH",
                f"usage={usage.validation_exposures} persisted={exposure_count}",
            )
        for lin in self._lineages.list_for_session(session_id):
            if lin.parent_lineage_id:
                parent = self._lineages.get(lin.parent_lineage_id)
                if parent is None:
                    raise MiningIntegrityError("BROKEN_LINEAGE_PARENT", lin.lineage_id)
        return {
            "session_id": session_id,
            "session_config_hash": row.session_config_hash,
            "budget_hash": row.budget_hash,
            "integrity_ok": True,
            "event_log_hash": computed,
            "exposure_count": exposure_count,
        }
