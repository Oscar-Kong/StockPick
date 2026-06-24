"""Hydrate persisted run detail, charts, and metric explanations for Results UI."""
from __future__ import annotations

import json
import math
from typing import Any

from data.db_engine import get_engine
from engines.quant_models import BacktestRun, FactorIcHistory, PairsResearchRun, ResearchRunIndex
from models.schemas_research import (
    ChartSeries,
    MetricExplanation,
    ResearchRunDetailResponse,
    ResearchRunListItem,
    ResearchRunSummary,
)
from services.evidence_memory_service import list_evidence_memory
from services.research_experiments_service import get_experiment
from services.research_ideas_service import get_idea
from services.research_run_interpretation_service import (
    build_interpretation,
    parse_stored_interpretation,
    persist_interpretation,
)
from services.research_run_service import _row_to_list_item, get_run, list_runs
from services.scan_evaluation_charts import charts_from_artifact
from sqlalchemy.orm import Session


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        f = float(value)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    except (TypeError, ValueError):
        return None


def load_detail_payload(summary: ResearchRunSummary) -> dict[str, Any]:
    ref = summary.result_reference
    store = ref.store
    run_id = ref.run_id or summary.run_id
    engine = get_engine()

    if store == "backtest_runs":
        with Session(engine) as session:
            row = session.get(BacktestRun, run_id)
            if not row:
                return {}
            config = json.loads(row.config_json or "{}")
            metrics = json.loads(row.metrics_json or "{}")
            return {
                "config": config,
                "summary": metrics,
                **metrics,
                **config,
                "started_at": row.started_at.isoformat() if row.started_at else None,
                "finished_at": row.finished_at.isoformat() if row.finished_at else None,
            }

    if store == "pairs_research_runs":
        with Session(engine) as session:
            row = session.get(PairsResearchRun, run_id)
            if not row:
                return {}
            config = json.loads(row.config_json or "{}")
            summary_data = json.loads(row.summary_json or "{}")
            pairs = json.loads(row.pairs_json or "[]")
            return {**config, **summary_data, "pairs": pairs}

    if store == "factor_ic_history" or summary.run_type == "factor_ic_panel":
        sleeve = summary.sleeve or summary.parameters.get("sleeve")
        as_of = summary.data_cutoff or summary.parameters.get("as_of_date")
        if not sleeve or not as_of:
            return {}
        with Session(engine) as session:
            rows = (
                session.query(FactorIcHistory)
                .filter(FactorIcHistory.sleeve == sleeve, FactorIcHistory.as_of_date == as_of)
                .all()
            )
            factors = [
                {
                    "factor_id": r.factor_id,
                    "ic": _safe_float(r.ic),
                    "ir": _safe_float(r.ir),
                    "horizon_days": r.horizon_days,
                    "sample_n": r.sample_n,
                }
                for r in rows
            ]
            ics = [f["ic"] for f in factors if f["ic"] is not None]
            mean_ic = sum(ics) / len(ics) if ics else None
            return {
                "sleeve": sleeve,
                "as_of_date": as_of,
                "factors": factors,
                "mean_ic": mean_ic,
                "sample_n": sum(int(r.sample_n or 0) for r in rows),
            }

    if summary.run_type == "prediction_outcomes":
        try:
            from services.trade_feedback_service import feedback_summary

            return dict(feedback_summary())
        except Exception:
            return {"outcomes_count": summary.sample_size or 0}

    return {}


def _line_series(points: list[dict[str, Any]], *, name: str = "series") -> list[dict[str, Any]]:
    safe = []
    for p in points:
        y = _safe_float(p.get("y"))
        if y is None and p.get("y") is not None:
            continue
        safe.append({"x": p.get("x"), "y": y, "label": p.get("label")})
    return [{"name": name, "data": safe}]


def build_charts(run_type: str, summary: ResearchRunSummary, detail: dict[str, Any]) -> list[ChartSeries]:
    charts: list[ChartSeries] = []

    if run_type == "walk_forward":
        periods = detail.get("periods") or []
        ic_points = []
        spread_points = []
        for i, p in enumerate(periods):
            if not isinstance(p, dict):
                continue
            label = p.get("period_end") or p.get("as_of") or str(i + 1)
            ic_points.append({"x": label, "y": _safe_float(p.get("rank_ic") or p.get("mean_rank_ic"))})
            spread_points.append({"x": label, "y": _safe_float(p.get("long_short_spread") or p.get("spread"))})
        charts.append(
            ChartSeries(
                chart_id="wf_rank_ic",
                title="Rank IC over time",
                chart_type="line",
                x_label="Period",
                y_label="Rank IC",
                series=_line_series(ic_points, name="Rank IC"),
                empty_reason="No period-level IC data persisted" if not ic_points else None,
            )
        )
        charts.append(
            ChartSeries(
                chart_id="wf_spread",
                title="Spread over time",
                chart_type="line",
                x_label="Period",
                y_label="Spread",
                series=_line_series(spread_points, name="Spread"),
                empty_reason="No spread series in run payload" if not spread_points else None,
            )
        )
        turnover = _safe_float(detail.get("mean_turnover"))
        charts.append(
            ChartSeries(
                chart_id="wf_turnover",
                title="Turnover",
                chart_type="bar",
                series=[{"name": "Mean turnover", "data": [{"x": "run", "y": turnover}]}],
                empty_reason="Turnover not recorded" if turnover is None else None,
            )
        )
        charts.append(
            ChartSeries(
                chart_id="wf_coverage",
                title="Coverage",
                chart_type="bar",
                series=[
                    {
                        "name": "Periods",
                        "data": [
                            {"x": "Scored", "y": detail.get("periods_scored")},
                            {"x": "Rebalance", "y": detail.get("rebalance_periods")},
                        ],
                    }
                ],
            )
        )

    elif run_type == "factor_ic_panel":
        factors = detail.get("factors") or []
        heat_rows = [
            {"x": f.get("factor_id"), "y": _safe_float(f.get("ic")), "label": f.get("horizon_days")}
            for f in factors
            if isinstance(f, dict)
        ]
        charts.append(
            ChartSeries(
                chart_id="factor_ic_heatmap",
                title="IC by factor",
                chart_type="heatmap",
                y_label="IC",
                series=[{"name": "IC", "data": heat_rows}],
                empty_reason="No factor IC rows" if not heat_rows else None,
            )
        )
        charts.append(
            ChartSeries(
                chart_id="factor_coverage",
                title="Coverage",
                chart_type="bar",
                series=[
                    {
                        "name": "Sample n",
                        "data": [{"x": f.get("factor_id"), "y": f.get("sample_n")} for f in factors if isinstance(f, dict)],
                    }
                ],
                empty_reason="No coverage data" if not factors else None,
            )
        )

    elif run_type == "pairs":
        pairs = detail.get("pairs") or []
        for pair in pairs[:1]:
            if not isinstance(pair, dict):
                continue
            z = _safe_float(pair.get("latest_z_score"))
            charts.append(
                ChartSeries(
                    chart_id="pairs_zscore",
                    title="Z-score with threshold guides",
                    chart_type="line",
                    y_label="Z-score",
                    series=[
                        {"name": "Z-score", "data": [{"x": "latest", "y": z}]},
                        {"name": "Entry (+2)", "data": [{"x": "latest", "y": 2.0}]},
                        {"name": "Entry (-2)", "data": [{"x": "latest", "y": -2.0}]},
                    ],
                    empty_reason="Z-score unavailable" if z is None else None,
                )
            )
        charts.append(
            ChartSeries(
                chart_id="pairs_spread",
                title="Spread summary",
                chart_type="bar",
                series=[
                    {
                        "name": "Pairs",
                        "data": [
                            {"x": "Qualifying", "y": detail.get("cointegrated_count")},
                            {"x": "Returned", "y": detail.get("pairs_returned")},
                        ],
                    }
                ],
            )
        )

    elif run_type == "prediction_outcomes":
        charts.append(
            ChartSeries(
                chart_id="pred_error",
                title="Mean forecast error",
                chart_type="bar",
                series=[
                    {
                        "name": "Error %",
                        "data": [{"x": "mean", "y": _safe_float(detail.get("mean_prediction_error_pct"))}],
                    }
                ],
                empty_reason="No resolved outcomes" if not detail.get("outcomes_count") else None,
            )
        )
        charts.append(
            ChartSeries(
                chart_id="pred_coverage",
                title="Resolution coverage",
                chart_type="bar",
                series=[
                    {
                        "name": "Outcomes",
                        "data": [{"x": "resolved", "y": detail.get("outcomes_count")}],
                    }
                ],
            )
        )

    elif run_type == "similar_signal":
        charts.append(
            ChartSeries(
                chart_id="similar_outcome",
                title="Outcome distribution",
                chart_type="bar",
                series=[
                    {
                        "name": "Avg forward return %",
                        "data": [{"x": "sample", "y": _safe_float(detail.get("avg_forward_return_pct"))}],
                    }
                ],
                empty_reason="No forward returns" if detail.get("avg_forward_return_pct") is None else None,
            )
        )

    elif run_type == "portfolio_policy":
        charts.append(
            ChartSeries(
                chart_id="policy_equity",
                title="Total return",
                chart_type="bar",
                series=[
                    {
                        "name": "Return %",
                        "data": [{"x": "total", "y": _safe_float(detail.get("total_return_pct"))}],
                    }
                ],
            )
        )
        charts.append(
            ChartSeries(
                chart_id="policy_drawdown",
                title="Max drawdown",
                chart_type="bar",
                series=[
                    {
                        "name": "Drawdown %",
                        "data": [{"x": "max", "y": _safe_float(detail.get("max_drawdown_pct"))}],
                    }
                ],
            )
        )

    elif run_type == "scan_evaluation":
        charts.extend(charts_from_artifact(detail))

    return charts


METRIC_EXPLANATIONS: dict[str, list[MetricExplanation]] = {
    "walk_forward": [
        MetricExplanation(
            metric_key="mean_rank_ic",
            label="Mean rank IC",
            measures="Spearman correlation between factor ranks and forward returns averaged across walk-forward periods.",
            preferred_direction="Higher positive values indicate stronger predictive ranking power.",
            why_it_matters="Stable positive rank IC supports factor edge persistence out of sample.",
            limitations="Sensitive to universe size, rebalance frequency, and single-regime windows.",
        ),
        MetricExplanation(
            metric_key="periods_scored",
            label="Periods scored",
            measures="Count of non-overlapping walk-forward evaluation periods with valid IC.",
            preferred_direction="More periods improve confidence, subject to gate minimums.",
            why_it_matters="Multiple periods reduce luck from a single favorable window.",
            limitations="Does not guarantee regime diversity or realistic trading costs.",
        ),
    ],
    "factor_ic_panel": [
        MetricExplanation(
            metric_key="mean_ic",
            label="Mean IC",
            measures="Cross-sectional correlation between factor exposures and forward returns for the panel date.",
            preferred_direction="Higher magnitude (positive or negative) indicates stronger linear relationship.",
            why_it_matters="IC panels summarize current factor efficacy for a sleeve.",
            limitations="Single-date snapshot; may not persist across regimes.",
        ),
    ],
    "pairs": [
        MetricExplanation(
            metric_key="cointegrated_count",
            label="Qualifying pairs",
            measures="Pairs passing cointegration threshold at the configured p-value.",
            preferred_direction="More qualifying pairs expand mean-reversion opportunities (research only).",
            why_it_matters="Validates whether spread relationships exist in the tested universe.",
            limitations="Historical cointegration does not guarantee future stability.",
        ),
    ],
    "prediction_outcomes": [
        MetricExplanation(
            metric_key="mean_prediction_error_pct",
            label="Mean forecast error %",
            measures="Average absolute gap between predicted and realized returns for resolved snapshots.",
            preferred_direction="Lower absolute error indicates better calibration.",
            why_it_matters="Links model recommendations to realized outcomes.",
            limitations="Depends on resolution coverage and horizon alignment.",
        ),
    ],
    "scan_evaluation": [
        MetricExplanation(
            metric_key="recall_at_10",
            label="Stage A Recall@10",
            measures="Share of realized top-decile forward performers captured in the Stage A shortlist (top 10).",
            preferred_direction="Higher recall indicates better early-stage ranking quality.",
            why_it_matters="Stage A gates expensive enrichment; recall measures whether strong names survive the filter.",
            limitations="Depends on universe size, horizon, and survivorship in historical data.",
        ),
        MetricExplanation(
            metric_key="mean_rank_ic",
            label="Mean rank IC",
            measures="Spearman correlation between ranking score and forward return across rebalance dates.",
            preferred_direction="Higher positive IC indicates scores align with realized outcomes.",
            why_it_matters="Summarizes monotonic relationship between score and forward performance.",
            limitations="Sensitive to outliers, thin universes, and regime shifts.",
        ),
    ],
}


def get_metric_explanations(run_type: str) -> list[MetricExplanation]:
    return list(METRIC_EXPLANATIONS.get(run_type, []))


def _related_runs(summary: ResearchRunSummary) -> list[ResearchRunSummary]:
    listed = list_runs(
        run_type=summary.run_type,
        sleeve=summary.sleeve,
        experiment_id=summary.experiment_id,
        backfill=False,
        limit=6,
    )
    return [r for r in listed.runs if r.run_id != summary.run_id][:5]


def _related_ideas(summary: ResearchRunSummary) -> list:
    from models.schemas_research import ResearchIdeaResponse

    ideas: list[ResearchIdeaResponse] = []
    if summary.idea_id:
        idea = get_idea(summary.idea_id)
        if idea:
            ideas.append(idea)
    if summary.experiment_id:
        exp = get_experiment(summary.experiment_id)
        if exp and exp.idea_id and exp.idea_id != summary.idea_id:
            idea = get_idea(exp.idea_id)
            if idea:
                ideas.append(idea)
    return ideas


def _skipped_data(summary: ResearchRunSummary, detail: dict[str, Any]) -> list[str]:
    skipped: list[str] = []
    for w in summary.warnings:
        if "skip" in w.lower() or "missing" in w.lower():
            skipped.append(w)
    notes = detail.get("notes") or detail.get("skipped") or []
    if isinstance(notes, list):
        skipped.extend(str(n) for n in notes)
    return skipped


def get_run_detail(run_id: str, *, refresh: bool = False, use_llm: bool | None = None) -> ResearchRunDetailResponse | None:
    summary = get_run(run_id)
    if not summary:
        return None

    engine = get_engine()
    interpretation_json: str | None = None
    with Session(engine) as session:
        row = session.get(ResearchRunIndex, run_id)
        list_item = _row_to_list_item(row) if row else ResearchRunListItem(**summary.model_dump())
        if row:
            interpretation_json = row.interpretation_json

    detail = load_detail_payload(summary)
    stored = parse_stored_interpretation(interpretation_json)
    if refresh or not stored:
        interpretation = build_interpretation(summary, detail, use_llm=use_llm)
        persist_interpretation(run_id, interpretation)
    else:
        interpretation = stored

    experiment = get_experiment(summary.experiment_id) if summary.experiment_id else None
    evidence = list_evidence_memory(run_id=run_id, limit=20)

    return ResearchRunDetailResponse(
        summary=list_item,
        interpretation=interpretation,
        experiment=experiment,
        detail=detail,
        charts=build_charts(summary.run_type, summary, detail),
        metric_explanations=get_metric_explanations(summary.run_type),
        evidence_memory=evidence.items,
        related_runs=_related_runs(summary),
        related_ideas=_related_ideas(summary),
        skipped_data=_skipped_data(summary, detail),
    )
