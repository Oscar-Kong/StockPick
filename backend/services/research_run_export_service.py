"""Export research run payloads — JSON and tabular CSV without secrets."""
from __future__ import annotations

import csv
import io
import json
from typing import Any

from models.schemas_research import ResearchRunDetailResponse
from services.research_run_detail_service import get_run_detail

_SECRET_KEYS = frozenset(
    {
        "api_key",
        "token",
        "password",
        "secret",
        "authorization",
        "stack_trace",
        "traceback",
    }
)


def _scrub(obj: Any) -> Any:
    if isinstance(obj, dict):
        cleaned: dict[str, Any] = {}
        for k, v in obj.items():
            if str(k).lower() in _SECRET_KEYS:
                continue
            cleaned[k] = _scrub(v)
        return cleaned
    if isinstance(obj, list):
        return [_scrub(x) for x in obj]
    if isinstance(obj, str) and ("Traceback" in obj or "api_key" in obj.lower()):
        return "[redacted]"
    return obj


def build_export_payload(run_id: str, *, refresh: bool = False) -> dict[str, Any] | None:
    detail = get_run_detail(run_id, refresh=refresh, use_llm=False)
    if not detail:
        return None
    s = detail.summary
    payload = {
        "run_id": s.run_id,
        "experiment_id": s.experiment_id,
        "run_type": s.run_type,
        "name": s.name,
        "status": s.status,
        "strategy_version": s.strategy_version,
        "factor_model_version": s.factor_model_version,
        "data_cutoff": s.data_cutoff,
        "parameters": s.parameters,
        "universe": s.universe,
        "primary_metrics": [m.model_dump() for m in s.primary_metrics],
        "warnings": s.warnings,
        "blockers": s.blockers,
        "verdict": detail.interpretation.verdict,
        "evidence_impact": detail.interpretation.evidence_impact,
        "reliability": detail.interpretation.reliability.model_dump(),
        "interpretation": detail.interpretation.model_dump(mode="json"),
        "detail": _scrub(detail.detail),
        "skipped_data": detail.skipped_data,
        "research_notes": s.research_notes,
    }
    return _scrub(payload)


def export_json(run_id: str, *, refresh: bool = False) -> str | None:
    payload = build_export_payload(run_id, refresh=refresh)
    if payload is None:
        return None
    return json.dumps(payload, indent=2, default=str)


def export_csv(run_id: str, *, refresh: bool = False) -> str | None:
    detail = get_run_detail(run_id, refresh=refresh, use_llm=False)
    if not detail:
        return None

    buf = io.StringIO()
    writer = csv.writer(buf)
    s = detail.summary

    writer.writerow(["section", "key", "value"])
    writer.writerow(["metadata", "run_id", s.run_id])
    writer.writerow(["metadata", "run_type", s.run_type])
    writer.writerow(["metadata", "name", s.name])
    writer.writerow(["metadata", "status", s.status])
    writer.writerow(["metadata", "data_cutoff", s.data_cutoff or ""])
    writer.writerow(["metadata", "strategy_version", s.strategy_version])
    writer.writerow(["metadata", "factor_model_version", s.factor_model_version])
    writer.writerow(["interpretation", "verdict", detail.interpretation.verdict])
    writer.writerow(["interpretation", "evidence_impact", detail.interpretation.evidence_impact])
    writer.writerow(["interpretation", "reliability_score", detail.interpretation.reliability.score])

    for m in s.primary_metrics:
        writer.writerow(["metric", m.label, m.value])

    for w in s.warnings:
        writer.writerow(["warning", w, ""])

    if s.run_type == "walk_forward":
        periods = detail.detail.get("periods") or []
        for i, p in enumerate(periods):
            if isinstance(p, dict):
                writer.writerow(["period", i + 1, json.dumps(_scrub(p))])

    if s.run_type == "factor_ic_panel":
        for f in detail.detail.get("factors") or []:
            if isinstance(f, dict):
                writer.writerow(["factor", f.get("factor_id"), f.get("ic")])

    if s.run_type == "pairs":
        for p in detail.detail.get("pairs") or []:
            if isinstance(p, dict):
                writer.writerow(["pair", ",".join(p.get("pair") or []), p.get("latest_z_score")])

    return buf.getvalue()
