"""Quant Lab adapter — runs existing scan evaluation harness without rewriting replay math."""
from __future__ import annotations

import logging
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from config import FACTOR_MODEL_VERSION, STRATEGY_VERSION
from services.scan_evaluation_replay import SUPPORTED_ALGORITHM_VERSIONS
from services.scan_evaluation_service import (
    ScanEvaluationConfig,
    compare_algorithm_versions,
    run_scan_evaluation,
    write_experiment_outputs,
)

logger = logging.getLogger(__name__)

StageCallback = Callable[[str, str, str], None]

DEFAULT_ALGORITHM_VERSIONS = ["alphabetical_baseline", "stage_a_v2"]
MAX_LOCAL_SYMBOLS = 80
MAX_LOCAL_REBALANCE_DATES = 24


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _parse_versions(merged: dict[str, Any]) -> list[str]:
    raw = merged.get("algorithm_versions")
    if isinstance(raw, str):
        raw = [v.strip() for v in raw.split(",") if v.strip()]
    if not raw:
        single = str(merged.get("algorithm_version") or "stage_a_v2")
        raw = [single]
    out: list[str] = []
    for v in raw:
        key = str(v).strip()
        if key and key not in out:
            out.append(key)
    return out


def config_from_merged(*, bucket: str, merged: dict[str, Any]) -> ScanEvaluationConfig:
    """Build ScanEvaluationConfig from Quant Lab merged parameters."""
    versions = _parse_versions(merged)
    return ScanEvaluationConfig(
        bucket=bucket,
        start_date=str(merged["start_date"]),
        end_date=str(merged["end_date"]),
        algorithm_version=versions[0],
        rebalance_frequency=str(merged.get("rebalance_frequency") or "monthly"),
        forward_horizons=[int(x) for x in (merged.get("forward_horizons") or [5, 20])],
        max_universe=int(merged.get("max_universe") or merged.get("max_symbols") or 25),
        stage_b_cap=int(merged.get("stage_b_cap") or 20),
        max_results=int(merged.get("max_results") or 10),
        stage_a_recall_caps=[int(x) for x in (merged.get("stage_a_recall_caps") or [10, 20, 50])],
        apply_penny_friction=bool(merged.get("apply_penny_friction", True)),
        spread_bps=float(merged.get("spread_bps") or merged.get("cost_assumption_bps") or 50.0),
        slippage_bps=float(merged.get("slippage_bps") or 25.0),
        scoring_version=str(merged.get("scoring_version") or FACTOR_MODEL_VERSION),
        strategy_version=str(merged.get("strategy_version") or STRATEGY_VERSION),
        output_dir=str(merged.get("output_dir") or "data/scan_eval"),
        experiment_label=str(merged.get("experiment_label") or versions[0]),
    )


class ScanEvaluationExperimentRunner:
    """Stable Quant Lab entry point over scan_evaluation_service."""

    def run(
        self,
        *,
        bucket: str,
        merged: dict[str, Any],
        on_stage: StageCallback | None = None,
        price_panel: dict | None = None,
    ) -> dict[str, Any]:
        versions = _parse_versions(merged)
        common = {
            "start_date": str(merged["start_date"]),
            "end_date": str(merged["end_date"]),
            "rebalance_frequency": str(merged.get("rebalance_frequency") or "monthly"),
            "forward_horizons": [int(x) for x in (merged.get("forward_horizons") or [5, 20])],
            "max_universe": int(merged.get("max_universe") or merged.get("max_symbols") or 25),
            "stage_b_cap": int(merged.get("stage_b_cap") or 20),
            "max_results": int(merged.get("max_results") or 10),
            "apply_penny_friction": bool(merged.get("apply_penny_friction", True)),
            "spread_bps": float(merged.get("spread_bps") or 50.0),
            "slippage_bps": float(merged.get("slippage_bps") or 25.0),
            "output_dir": str(merged.get("output_dir") or "data/scan_eval"),
            "price_panel": price_panel,
        }

        if on_stage:
            on_stage("preparing_universe", "running", f"Versions: {', '.join(versions)}")

        if len(versions) >= 2:
            if on_stage:
                on_stage("replaying_scans", "running", "Replaying historical scans per algorithm")
            comparison = compare_algorithm_versions(bucket=bucket, versions=versions, **common)
            if on_stage:
                on_stage("comparing_algorithms", "completed", f"Compared {len(versions)} versions")
            return _finalize_comparison(comparison, bucket=bucket, merged=merged, versions=versions)
        cfg = config_from_merged(bucket=bucket, merged=merged)
        if price_panel is not None:
            cfg.price_panel = price_panel
        if on_stage:
            on_stage("loading_historical_data", "running", "Loading OHLC panel")
            on_stage("replaying_scans", "running", f"Algorithm: {cfg.algorithm_version}")
        payload = run_scan_evaluation(cfg)
        if on_stage:
            on_stage("calculating_forward_outcomes", "completed", "Forward labels attached")
        return _finalize_single(payload, bucket=bucket, merged=merged, version=cfg.algorithm_version)


def _artifact_dir(run_id: str) -> Path:
    return Path("data/scan_eval") / run_id


def _finalize_single(payload: dict[str, Any], *, bucket: str, merged: dict[str, Any], version: str) -> dict[str, Any]:
    run_id = f"scan_evaluation:{uuid.uuid4().hex[:12]}"
    payload["run_id"] = run_id
    payload["run_type"] = "scan_evaluation"
    payload["bucket"] = bucket
    payload["algorithm_versions"] = [version]
    payload["comparison"] = None
    out_dir = _artifact_dir(run_id)
    paths = write_experiment_outputs(payload, out_dir)
    from services.scan_evaluation_service import build_chart_series

    charts = build_chart_series(payload)
    charts_path = out_dir / "charts.json"
    import json

    charts_path.write_text(json.dumps(charts, indent=2), encoding="utf-8")
    paths["charts"] = str(charts_path)
    payload["charts"] = charts
    payload["artifact_paths"] = paths
    payload["quant_lab"] = build_quant_lab_summary(payload, comparison=None)
    return payload


def _finalize_comparison(
    comparison: dict[str, Any],
    *,
    bucket: str,
    merged: dict[str, Any],
    versions: list[str],
) -> dict[str, Any]:
    run_id = f"scan_evaluation:{uuid.uuid4().hex[:12]}"
    out_dir = _artifact_dir(run_id)
    out_dir.mkdir(parents=True, exist_ok=True)

    per_version_paths: dict[str, dict[str, str]] = {}
    for ver, run in comparison.get("full_runs", {}).items():
        run["run_id"] = run_id
        paths = write_experiment_outputs(run, out_dir / ver)
        per_version_paths[ver] = paths

    charts = build_comparison_charts(comparison, versions)
    charts_path = out_dir / "charts.json"
    charts_path.write_text(__import__("json").dumps(charts, indent=2), encoding="utf-8")

    payload = {
        "run_id": run_id,
        "run_type": "scan_evaluation",
        "comparison_id": comparison.get("comparison_id"),
        "created_at": comparison.get("created_at"),
        "bucket": bucket,
        "algorithm_versions": versions,
        "config": {k: v for k, v in merged.items() if k != "price_panel"},
        "comparison": {
            "versions": versions,
            "summaries": comparison.get("runs") or {},
            "metrics_table": build_comparison_metrics_table(comparison, versions),
        },
        "full_runs": comparison.get("full_runs"),
        "caveats": _collect_caveats(comparison),
        "artifact_paths": {
            "root": str(out_dir),
            "charts": str(charts_path),
            "per_version": per_version_paths,
        },
        "production_impact": "none — evidence only",
        "purpose": "offline_scan_selection_evaluation",
    }
    payload["quant_lab"] = build_quant_lab_summary(payload, comparison=comparison)
    summary_path = out_dir / "summary.json"
    summary_path.write_text(__import__("json").dumps(payload, indent=2, default=str), encoding="utf-8")
    payload["artifact_paths"]["summary"] = str(summary_path)
    return payload


def _collect_caveats(comparison: dict[str, Any]) -> list[str]:
    caveats = [
        "Evaluation experiments do not automatically modify the production scan configuration.",
    ]
    for run in (comparison.get("full_runs") or {}).values():
        for c in run.get("caveats") or []:
            if c not in caveats:
                caveats.append(c)
    return caveats


def build_comparison_metrics_table(comparison: dict[str, Any], versions: list[str]) -> list[dict[str, Any]]:
    """Rows for algorithm-version comparison table."""
    rows: list[dict[str, Any]] = []
    summaries = comparison.get("runs") or {}
    for ver in versions:
        s = summaries.get(ver) or {}
        sa = s.get("stage_a_recall") or {}
        h = s.get("horizons") or {}
        h20 = h.get("20") or h.get(str(list(h.keys())[0])) if h else {}
        rows.append(
            {
                "algorithm_version": ver,
                "rebalance_count": s.get("rebalance_count"),
                "recall_at_10": sa.get("mean_recall_at_10"),
                "recall_at_20": sa.get("mean_recall_at_20"),
                "recall_at_50": sa.get("mean_recall_at_50"),
                "mean_rank_ic_20": h20.get("mean_rank_ic"),
                "mean_hit_rate_20": h20.get("mean_hit_rate"),
                "mean_avg_forward_return_20": h20.get("mean_avg_forward_return_pct"),
                "mean_turnover_20": h20.get("mean_turnover"),
            }
        )
    return rows


def build_quant_lab_summary(payload: dict[str, Any], *, comparison: dict[str, Any] | None) -> dict[str, Any]:
    """Compact metrics block for ResearchRun index."""
    if comparison:
        table = build_comparison_metrics_table(comparison, payload.get("algorithm_versions") or [])
        return {
            "mode": "comparison",
            "algorithm_versions": payload.get("algorithm_versions"),
            "comparison_table": table,
            "rebalance_count": max((r.get("rebalance_count") or 0) for r in table) if table else 0,
        }
    summary = payload.get("summary") or {}
    sa = summary.get("stage_a_recall") or {}
    return {
        "mode": "single",
        "algorithm_version": (payload.get("algorithm_versions") or [None])[0],
        "rebalance_count": summary.get("rebalance_count"),
        "recall_at_10": sa.get("mean_recall_at_10"),
        "recall_at_20": sa.get("mean_recall_at_20"),
        "horizons": summary.get("horizons"),
    }


def build_comparison_charts(comparison: dict[str, Any], versions: list[str]) -> dict[str, Any]:
    """Extended chart JSON for multi-version comparisons."""
    from services.scan_evaluation_service import build_chart_series

    charts: dict[str, Any] = {
        "recall_by_version": [],
        "hit_rate_by_horizon": [],
        "mean_rank_ic_by_horizon": [],
        "decile_forward_returns": [],
    }
    summaries = comparison.get("runs") or {}
    for ver in versions:
        s = summaries.get(ver) or {}
        sa = s.get("stage_a_recall") or {}
        charts["recall_by_version"].append(
            {
                "version": ver,
                "recall_at_10": sa.get("mean_recall_at_10"),
                "recall_at_20": sa.get("mean_recall_at_20"),
                "recall_at_50": sa.get("mean_recall_at_50"),
            }
        )
        for hkey, block in (s.get("horizons") or {}).items():
            charts["hit_rate_by_horizon"].append(
                {"version": ver, "horizon": hkey, "hit_rate": block.get("mean_hit_rate")}
            )
            charts["mean_rank_ic_by_horizon"].append(
                {"version": ver, "horizon": hkey, "mean_rank_ic": block.get("mean_rank_ic")}
            )
        full = (comparison.get("full_runs") or {}).get(ver) or {}
        sub = build_chart_series(full)
        for pt in sub.get("decile_forward_returns") or []:
            pt = dict(pt)
            pt["version"] = ver
            charts["decile_forward_returns"].append(pt)
    return charts


def validate_scan_evaluation_params(merged: dict[str, Any]) -> list[str]:
    """Return error messages (empty if ok)."""
    errors: list[str] = []
    start = merged.get("start_date")
    end = merged.get("end_date")
    if not start or not end:
        errors.append("start_date and end_date are required")
    else:
        try:
            from datetime import date

            if date.fromisoformat(str(end)) <= date.fromisoformat(str(start)):
                errors.append("end_date must be after start_date")
        except ValueError:
            errors.append("Invalid ISO date format")
    for ver in _parse_versions(merged):
        if ver not in SUPPORTED_ALGORITHM_VERSIONS:
            errors.append(f"Unsupported algorithm_version: {ver}")
    horizons = merged.get("forward_horizons") or [5, 20]
    if not horizons or any(int(h) <= 0 for h in horizons):
        errors.append("forward_horizons must be positive integers")
    max_u = int(merged.get("max_universe") or merged.get("max_symbols") or 25)
    if max_u > MAX_LOCAL_SYMBOLS:
        errors.append(f"max_universe {max_u} exceeds local cap {MAX_LOCAL_SYMBOLS}")
    bucket = str(merged.get("bucket") or "")
    if bucket not in ("penny", "compounder"):
        errors.append("bucket must be penny or compounder")
    return errors
