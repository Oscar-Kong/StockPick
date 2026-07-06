"""Durable experiment run monitoring for mining sessions."""
from __future__ import annotations

from services.factor_discovery.artifact_integrity import load_and_verify_artifact_record
from services.factor_discovery.mining.models import LineageStatus, RunMonitorStatus
from services.factor_discovery.repositories import FactorDiscoveryRunRepository, FactorValidationArtifactRepository


def map_run_monitor_status(run_status: str | None, *, has_artifact: bool, indexed: bool) -> RunMonitorStatus:
    if run_status in {None, "pending", "queued"}:
        return RunMonitorStatus.QUEUED
    if run_status == "running":
        return RunMonitorStatus.RUNNING
    if run_status == "failed":
        return RunMonitorStatus.FAILED
    if run_status == "cancelled":
        return RunMonitorStatus.CANCELLED
    if run_status == "completed" and not has_artifact:
        return RunMonitorStatus.ARTIFACT_PENDING
    if run_status == "completed" and has_artifact and not indexed:
        return RunMonitorStatus.INDEX_PENDING
    if run_status == "completed":
        return RunMonitorStatus.COMPLETE
    return RunMonitorStatus.CREATED


class MiningMonitorStep:
    def __init__(self) -> None:
        self._runs = FactorDiscoveryRunRepository()
        self._artifacts = FactorValidationArtifactRepository()

    def inspect_run(self, run_id: str) -> dict:
        run = self._runs.get(run_id)
        if run is None:
            return {"run_id": run_id, "monitor_status": RunMonitorStatus.CANCELLED.value, "complete": False}
        artifact_id = None
        integrity_ok = False
        if run.closed_artifact_hash:
            art = self._artifacts.get_by_hash(run.closed_artifact_hash)
            if art:
                artifact_id = art.artifact_id
                try:
                    load_and_verify_artifact_record(art)
                    integrity_ok = True
                except Exception:
                    integrity_ok = False
        monitor = map_run_monitor_status(
            run.status,
            has_artifact=artifact_id is not None,
            indexed=bool(run.status == "completed"),
        )
        return {
            "run_id": run_id,
            "run_status": run.status,
            "monitor_status": monitor.value,
            "artifact_id": artifact_id,
            "integrity_ok": integrity_ok,
            "complete": monitor == RunMonitorStatus.COMPLETE,
            "failed": monitor == RunMonitorStatus.FAILED,
            "infrastructure_failure": run.error_code in {"RUNNER_FAILURE", "PANEL_FAILED"} if run.error_code else False,
        }

    def lineage_status_for_monitor(self, monitor: dict, *, session_cancelled: bool) -> str:
        if session_cancelled and monitor.get("complete"):
            return LineageStatus.COMPLETED_AFTER_SESSION_CANCELLATION.value
        if monitor.get("complete") and monitor.get("integrity_ok"):
            return LineageStatus.VALIDATION_COMPLETED.value
        if monitor.get("failed"):
            if monitor.get("infrastructure_failure"):
                return LineageStatus.RUN_FAILED.value
            return LineageStatus.RUN_FAILED.value
        return LineageStatus.RUNNING.value
