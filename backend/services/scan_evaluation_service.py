"""Orchestrate offline scan evaluation experiments and write reports."""
from __future__ import annotations

import csv
import json
import logging
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import FACTOR_MODEL_VERSION, STRATEGY_VERSION
from services.scan_evaluation_metrics import aggregate_experiment_summary, aggregate_ranking_quality
from services.scan_evaluation_pit import DEFAULT_FORWARD_HORIZONS, load_price_panel_from_store
from services.scan_evaluation_replay import ReplayConfig, replay_scan_date
from services.walk_forward_research_service import rebalance_dates

logger = logging.getLogger(__name__)


@dataclass
class ScanEvaluationConfig:
    bucket: str
    start_date: str
    end_date: str
    algorithm_version: str = "stage_a_v2"
    rebalance_frequency: str = "monthly"
    forward_horizons: list[int] = field(default_factory=lambda: list(DEFAULT_FORWARD_HORIZONS))
    max_universe: int = 40
    stage_b_cap: int = 30
    max_results: int = 15
    stage_a_recall_caps: list[int] = field(default_factory=lambda: [10, 20, 50])
    apply_penny_friction: bool = True
    spread_bps: float = 50.0
    slippage_bps: float = 25.0
    scoring_version: str = FACTOR_MODEL_VERSION
    strategy_version: str = STRATEGY_VERSION
    output_dir: str = "data/scan_eval"
    experiment_label: str | None = None
    price_panel: dict | None = None  # inject for tests


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat()


def _experiment_id(cfg: ScanEvaluationConfig) -> str:
    label = cfg.experiment_label or cfg.algorithm_version
    return f"scan_eval_{cfg.bucket}_{label}_{uuid.uuid4().hex[:10]}"


def run_scan_evaluation(config: ScanEvaluationConfig) -> dict[str, Any]:
    """
    Run historical scan replay across rebalance dates.

    Does NOT modify production scan configuration or rankings.
    """
    dates = rebalance_dates(config.start_date, config.end_date, config.rebalance_frequency)
    if not dates:
        raise ValueError("No rebalance dates in range — widen window or check calendar data")

    from services.walk_forward_research_service import universe_for_date

    # Load panel for union of symbols seen across dates
    symbols: set[str] = set()
    for d in dates[:3]:
        syms, _ = universe_for_date(config.bucket, d, max_symbols=config.max_universe)
        symbols.update(syms)
    for d in dates[3:]:
        syms, _ = universe_for_date(config.bucket, d, max_symbols=config.max_universe)
        symbols.update(syms)

    if config.price_panel is not None:
        price_panel = config.price_panel
    else:
        price_panel = load_price_panel_from_store(sorted(symbols), limit=800)

    if not price_panel:
        raise ValueError(
            "No OHLC in HistoricalStore for evaluation universe. "
            "Run a scan or ingest quotes first, or inject price_panel in tests."
        )

    experiment_id = _experiment_id(config)
    snapshots: list[dict[str, Any]] = []
    prev_top: set[str] | None = None
    all_candidates: list[dict[str, Any]] = []

    for scan_date in dates:
        replay_cfg = ReplayConfig(
            bucket=config.bucket,
            scan_date=scan_date.isoformat(),
            algorithm_version=config.algorithm_version,
            stage_b_cap=config.stage_b_cap,
            max_results=config.max_results,
            forward_horizons=config.forward_horizons,
            max_universe=config.max_universe,
            apply_penny_friction=config.apply_penny_friction,
            spread_bps=config.spread_bps,
            slippage_bps=config.slippage_bps,
            scoring_version=config.scoring_version,
            strategy_version=config.strategy_version,
            stage_a_recall_caps=config.stage_a_recall_caps,
        )
        snap = replay_scan_date(price_panel=price_panel, config=replay_cfg)
        ranking_quality: dict[str, Any] = {}
        for h in config.forward_horizons:
            ranking_quality[str(h)] = aggregate_ranking_quality(
                snap["candidates"],
                horizon=h,
                prev_top_symbols=prev_top,
            )
        snap["ranking_quality"] = ranking_quality
        snapshots.append(snap)

        if snap["candidates"]:
            top_n = max(1, len(snap["candidates"]) // 5)
            prev_top = {
                c["symbol"]
                for c in sorted(
                    snap["candidates"],
                    key=lambda x: -(x.get("ranking_score") or 0),
                )[:top_n]
            }
        for c in snap["candidates"]:
            all_candidates.append({**c, "experiment_id": experiment_id, "algorithm_version": config.algorithm_version})

    summary = aggregate_experiment_summary(snapshots, horizons=config.forward_horizons)
    payload = {
        "experiment_id": experiment_id,
        "created_at": _utcnow_iso(),
        "purpose": "offline_scan_selection_evaluation",
        "production_impact": "none — evidence only",
        "config": {
            **asdict(config),
            "price_panel": None,
        },
        "rebalance_dates": [d.isoformat() for d in dates],
        "summary": summary,
        "snapshots": snapshots,
        "caveats": list(
            dict.fromkeys(
                c
                for s in snapshots
                for c in s.get("caveats", [])
            )
        ),
    }
    return payload


def write_experiment_outputs(result: dict[str, Any], output_dir: str | Path) -> dict[str, str]:
    """Write JSON summary, CSV candidates, Markdown report; optional chart JSON."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    exp_id = result["experiment_id"]
    paths: dict[str, str] = {}

    json_path = out / f"{exp_id}_summary.json"
    json_path.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    paths["json"] = str(json_path)

    csv_path = out / f"{exp_id}_candidates.csv"
    rows: list[dict[str, Any]] = []
    for snap in result.get("snapshots", []):
        for c in snap.get("candidates", []):
            flat = {
                "experiment_id": exp_id,
                "scan_date": snap.get("scan_date"),
                "algorithm_version": snap.get("algorithm_version"),
                "symbol": c.get("symbol"),
                "ranking_score": c.get("ranking_score"),
                "alpha_score": c.get("alpha_score"),
                "confidence_score": c.get("confidence_score"),
                "tradability_score": c.get("tradability_score"),
                "sector": c.get("sector"),
            }
            for h, fo in (c.get("forward_outcomes") or {}).items():
                flat[f"fwd_{h}d_pct"] = fo.get("forward_return_pct")
                flat[f"fwd_{h}d_adj_pct"] = fo.get("forward_return_adj_pct")
                flat[f"mae_{h}d_pct"] = fo.get("mae_pct")
                flat[f"mfe_{h}d_pct"] = fo.get("mfe_pct")
            rows.append(flat)

    if rows:
        fieldnames = sorted({k for r in rows for k in r.keys()})
        with csv_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
    paths["csv"] = str(csv_path)

    md_path = out / f"{exp_id}_report.md"
    md_path.write_text(render_markdown_report(result), encoding="utf-8")
    paths["markdown"] = str(md_path)

    chart_path = out / f"{exp_id}_charts.json"
    chart_path.write_text(json.dumps(build_chart_series(result), indent=2), encoding="utf-8")
    paths["charts"] = str(chart_path)

    return paths


def build_chart_series(result: dict[str, Any]) -> dict[str, Any]:
    """ChartSeries-compatible payload for Quant Lab / ResultChart."""
    cfg = result.get("config") or {}
    horizons = cfg.get("forward_horizons") or [20]
    h20 = str(horizons[-1] if 20 not in horizons else 20)
    decile_points: list[dict[str, Any]] = []
    for snap in result.get("snapshots", []):
        rq = (snap.get("ranking_quality") or {}).get(h20, {})
        dec = rq.get("deciles") or {}
        if not dec.get("sufficient"):
            continue
        for row in dec.get("deciles", []):
            decile_points.append(
                {
                    "date": snap.get("scan_date"),
                    "decile": row.get("decile"),
                    "avg_forward_return_pct": row.get("avg_forward_return_pct"),
                }
            )
    summary = result.get("summary") or {}
    ic_series = [
        {"horizon": h, "mean_rank_ic": (summary.get("horizons") or {}).get(h, {}).get("mean_rank_ic")}
        for h in [str(x) for x in horizons]
    ]
    return {
        "decile_forward_returns": decile_points,
        "mean_rank_ic_by_horizon": ic_series,
    }


def render_markdown_report(result: dict[str, Any]) -> str:
    cfg = result.get("config") or {}
    summary = result.get("summary") or {}
    lines = [
        f"# Scan evaluation report — `{result.get('experiment_id')}`",
        "",
        f"**Created:** {result.get('created_at')}  ",
        f"**Bucket:** {cfg.get('bucket')}  ",
        f"**Algorithm:** {cfg.get('algorithm_version')}  ",
        f"**Scoring version:** {cfg.get('scoring_version')}  ",
        f"**Strategy version:** {cfg.get('strategy_version')}  ",
        f"**Window:** {cfg.get('start_date')} → {cfg.get('end_date')} ({summary.get('rebalance_count', 0)} rebalance dates)",
        "",
        "> This harness measures whether Stage A/B rank useful candidates. "
        "It does **not** auto-update production scan settings.",
        "",
        "## Summary by horizon",
        "",
        "| Horizon (sessions) | Mean rank IC | Hit rate | Top−bottom spread | Avg fwd return | Turnover |",
        "|---:|---:|---:|---:|---:|---:|",
    ]
    for h, block in (summary.get("horizons") or {}).items():
        lines.append(
            f"| {h} | {block.get('mean_rank_ic')} | {block.get('mean_hit_rate')} | "
            f"{block.get('mean_top_minus_bottom_spread_pct')} | {block.get('mean_avg_forward_return_pct')} | "
            f"{block.get('mean_turnover')} |"
        )

    sa = summary.get("stage_a_recall") or {}
    lines.extend(
        [
            "",
            "## Stage A recall",
            "",
            f"- Mean Recall@10: **{sa.get('mean_recall_at_10')}**",
            f"- Mean Recall@20: **{sa.get('mean_recall_at_20')}**",
            "",
            "## Caveats",
            "",
        ]
    )
    for c in result.get("caveats") or []:
        lines.append(f"- {c}")

    lines.extend(["", "## Output files", "", "- JSON summary, CSV candidates, chart JSON alongside this report.", ""])
    return "\n".join(lines)


def compare_algorithm_versions(
    *,
    bucket: str,
    start_date: str,
    end_date: str,
    versions: list[str],
    **kwargs: Any,
) -> dict[str, Any]:
    """Run the same window for multiple algorithm_version labels."""
    runs: dict[str, Any] = {}
    for ver in versions:
        cfg = ScanEvaluationConfig(
            bucket=bucket,
            start_date=start_date,
            end_date=end_date,
            algorithm_version=ver,
            experiment_label=ver,
            **kwargs,
        )
        runs[ver] = run_scan_evaluation(cfg)
    return {
        "comparison_id": f"scan_eval_compare_{uuid.uuid4().hex[:10]}",
        "created_at": _utcnow_iso(),
        "versions": versions,
        "runs": {k: v.get("summary") for k, v in runs.items()},
        "full_runs": runs,
    }
