#!/usr/bin/env python3
"""Offline scan selection evaluation — historical replay with forward-return labels.

Does NOT modify production scan rankings. Produces JSON, CSV, Markdown, and chart JSON.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate scan Stage A/B ranking offline (no production changes)",
    )
    parser.add_argument("--bucket", required=True, help="penny | medium | compounder")
    parser.add_argument("--start-date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--end-date", required=True, help="YYYY-MM-DD")
    parser.add_argument(
        "--algorithm-version",
        default="stage_a_v2",
        choices=[
            "alphabetical_baseline",
            "stage_a_v1",
            "stage_a_v2",
            "scoring_engine_v1",
        ],
        help="Ranking pipeline variant to evaluate",
    )
    parser.add_argument(
        "--compare-versions",
        default="",
        help="Comma-separated versions to compare (overrides --algorithm-version)",
    )
    parser.add_argument("--rebalance-frequency", default="monthly")
    parser.add_argument(
        "--forward-horizons",
        default="1,5,20,60",
        help="Trading-session forward horizons",
    )
    parser.add_argument("--max-universe", type=int, default=40, help="Cap symbols per rebalance (MacBook-friendly)")
    parser.add_argument("--stage-b-cap", type=int, default=30)
    parser.add_argument("--max-results", type=int, default=15)
    parser.add_argument("--output-dir", default="data/scan_eval")
    parser.add_argument("--no-penny-friction", action="store_true")
    parser.add_argument("--spread-bps", type=float, default=50.0)
    parser.add_argument("--slippage-bps", type=float, default=25.0)
    args = parser.parse_args()

    horizons = [int(x.strip()) for x in args.forward_horizons.split(",") if x.strip()]
    if not horizons:
        raise SystemExit("forward-horizons must list at least one integer")

    from data.cache import init_db

    init_db()
    try:
        from engines.quant_db import init_quant_db

        init_quant_db()
    except Exception:
        pass

    from services.scan_evaluation_service import (
        ScanEvaluationConfig,
        compare_algorithm_versions,
        run_scan_evaluation,
        write_experiment_outputs,
    )

    common = dict(
        forward_horizons=horizons,
        max_universe=args.max_universe,
        stage_b_cap=args.stage_b_cap,
        max_results=args.max_results,
        apply_penny_friction=not args.no_penny_friction,
        spread_bps=args.spread_bps,
        slippage_bps=args.slippage_bps,
        output_dir=args.output_dir,
        rebalance_frequency=args.rebalance_frequency,
    )

    if args.compare_versions.strip():
        versions = [v.strip() for v in args.compare_versions.split(",") if v.strip()]
        comparison = compare_algorithm_versions(
            bucket=args.bucket,
            start_date=args.start_date,
            end_date=args.end_date,
            versions=versions,
            **common,
        )
        out_dir = Path(args.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        cmp_path = out_dir / f"{comparison['comparison_id']}.json"
        cmp_path.write_text(json.dumps(comparison, indent=2, default=str), encoding="utf-8")
        for ver, run in comparison["full_runs"].items():
            write_experiment_outputs(run, args.output_dir)
        print(json.dumps({"comparison_id": comparison["comparison_id"], "path": str(cmp_path)}, indent=2))
        return

    cfg = ScanEvaluationConfig(
        bucket=args.bucket,
        start_date=args.start_date,
        end_date=args.end_date,
        algorithm_version=args.algorithm_version,
        **common,
    )
    result = run_scan_evaluation(cfg)
    paths = write_experiment_outputs(result, args.output_dir)
    print(json.dumps({"experiment_id": result["experiment_id"], "outputs": paths, "summary": result["summary"]}, indent=2))


if __name__ == "__main__":
    main()
