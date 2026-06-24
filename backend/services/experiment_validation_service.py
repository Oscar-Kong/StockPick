"""Pre-run validation for experiment studio."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from config import DEMO_MODE, SCORE_ENGINE_V2_ENABLED
from models.schemas_research import ExperimentValidateRequest, ExperimentValidationCheck, ExperimentValidationResponse
from services.experiment_presets_service import merge_parameters, preset_allows_major_evidence, TEMPLATE_META
from services.experiment_universe_service import resolve_universe


def _default_hypotheses(experiment_type: str) -> tuple[str, str, str, str]:
    defaults = {
        "factor_validation": (
            "Selected factors show stable positive rank IC in the target sleeve.",
            "Factor IC is indistinguishable from noise (IC ≈ 0).",
            "Mean rank IC > 0.02 with adequate sample size across horizons.",
            "IC negative or sample size below preset minimum.",
        ),
        "walk_forward": (
            "Ranking model produces positive out-of-sample rank IC.",
            "Out-of-sample rank IC is zero or negative.",
            "Positive mean rank IC with acceptable turnover after costs.",
            "Rank IC flips sign across horizons or turnover excessive.",
        ),
        "prediction_calibration": (
            "Forecast errors are within acceptable bounds by recommendation tier.",
            "Systematic forecast bias exists across horizons.",
            "Mean absolute error below threshold with sufficient resolved outcomes.",
            "High unresolved rate or category error above threshold.",
        ),
        "pairs_discovery": (
            "Identified pairs show statistically significant cointegration.",
            "Pairs are spurious with no mean-reverting spread.",
            "Pairs pass p-value threshold with practical half-life.",
            "Half-life impractical or too many symbols excluded.",
        ),
        "similar_signal": (
            "Historical analogs show positive forward returns for similar factor profiles.",
            "Analog sample has no edge vs baseline.",
            "Win rate and median return positive with adequate sample.",
            "Sample too small or downside tail unacceptable.",
        ),
        "portfolio_policy": (
            "Policy backtest beats benchmark on risk-adjusted basis.",
            "Policy does not outperform equal-weight benchmark.",
            "Positive excess return with controlled drawdown and turnover.",
            "Drawdown or costs erase gross spread.",
        ),
    }
    return defaults.get(
        experiment_type,
        ("Research hypothesis", "Null hypothesis", "Success criteria", "Failure criteria"),
    )


def validate_experiment(body: ExperimentValidateRequest) -> ExperimentValidationResponse:
    exp_type = body.experiment_type
    merged = merge_parameters(exp_type, body.preset, body.parameters)
    checks: list[ExperimentValidationCheck] = []
    limitations: list[str] = []
    dependencies = {
        "score_engine_v2": bool(SCORE_ENGINE_V2_ENABLED),
        "demo_mode": not bool(DEMO_MODE),
        "research_api": True,
    }

    if DEMO_MODE:
        limitations.append("Demo mode limits symbol counts and persistence.")
        checks.append(
            ExperimentValidationCheck(
                key="demo_mode",
                label="Demo mode",
                value=True,
                status="warning",
                detail="Some persistence and symbol limits apply.",
            )
        )

    if exp_type == "prediction_calibration" and not bool(SCORE_ENGINE_V2_ENABLED):
        dependencies["score_engine_v2"] = False
        checks.append(
            ExperimentValidationCheck(
                key="score_engine_v2",
                label="Score engine v2",
                status="error",
                detail="SCORE_ENGINE_V2_ENABLED is false.",
            )
        )

    symbols, source, uni_warnings = resolve_universe(
        body.universe_definition, sleeve=body.sleeve, parameters=merged
    )
    for w in uni_warnings:
        limitations.append(w)

    checks.append(
        ExperimentValidationCheck(
            key="universe_source",
            label="Universe source",
            value=source,
            status="ok" if symbols else "error",
            detail=f"{len(symbols)} symbols resolved",
        )
    )

    symbol_count = len(symbols)
    min_symbols = 2 if exp_type in ("pairs_discovery", "portfolio_policy") else 1
    if exp_type == "similar_signal":
        sym = merged.get("symbol") or (symbols[0] if symbols else None)
        if sym:
            symbol_count = 1
            checks.append(
                ExperimentValidationCheck(
                    key="target_symbol",
                    label="Target symbol",
                    value=str(sym),
                    status="ok",
                )
            )
        else:
            checks.append(
                ExperimentValidationCheck(
                    key="target_symbol",
                    label="Target symbol",
                    status="error",
                    detail="Symbol required for similar-signal replay.",
                )
            )

    if symbol_count < min_symbols and exp_type not in ("prediction_calibration", "factor_validation"):
        checks.append(
            ExperimentValidationCheck(
                key="symbol_count",
                label="Symbol count",
                value=symbol_count,
                status="error",
                detail=f"Need at least {min_symbols} symbols.",
            )
        )
    else:
        checks.append(
            ExperimentValidationCheck(
                key="symbol_count",
                label="Symbol count",
                value=symbol_count,
                status="ok",
            )
        )

    if exp_type == "factor_validation":
        factors = merged.get("factors") or merged.get("factor_ids") or []
        if isinstance(factors, str):
            factors = [factors]
        if not factors:
            checks.append(
                ExperimentValidationCheck(
                    key="factors",
                    label="Factors",
                    status="error",
                    detail="Select at least one factor.",
                )
            )
        else:
            checks.append(
                ExperimentValidationCheck(
                    key="factors",
                    label="Factors",
                    value=len(factors),
                    status="ok",
                    detail=", ".join(str(f) for f in factors[:5]),
                )
            )

    if exp_type in ("walk_forward", "factor_validation"):
        start = merged.get("start_date")
        end = merged.get("end_date")
        if not start or not end:
            today = date.today()
            merged.setdefault("end_date", today.isoformat())
            merged.setdefault("start_date", (today - timedelta(days=365)).isoformat())
            checks.append(
                ExperimentValidationCheck(
                    key="date_range",
                    label="Date range",
                    status="warning",
                    detail="Using default 1y range.",
                )
            )
        else:
            try:
                sd = date.fromisoformat(str(start))
                ed = date.fromisoformat(str(end))
                ok = ed > sd
                checks.append(
                    ExperimentValidationCheck(
                        key="date_range",
                        label="Date range",
                        value=f"{start} → {end}",
                        status="ok" if ok else "error",
                    )
                )
            except ValueError:
                checks.append(
                    ExperimentValidationCheck(
                        key="date_range",
                        label="Date range",
                        status="error",
                        detail="Invalid ISO dates.",
                    )
                )

    expected_periods: int | None = None
    if exp_type == "walk_forward":
        expected_periods = int(merged.get("wf_min_periods") or 4)
        checks.append(
            ExperimentValidationCheck(
                key="expected_periods",
                label="Expected WF periods",
                value=expected_periods,
                status="ok",
            )
        )

    missing_data_rate: float | None = None
    if symbol_count > 0 and exp_type in ("pairs_discovery", "portfolio_policy", "walk_forward"):
        # Lightweight proxy — full price audit happens at launch
        missing_data_rate = 0.0
        checks.append(
            ExperimentValidationCheck(
                key="missing_data_rate",
                label="Missing data rate (estimate)",
                value=0.0,
                status="ok",
                detail="Full check runs at launch.",
            )
        )

    data_cutoff = merged.get("end_date") or date.today().isoformat()

    hyp, null_h, success, failure = _default_hypotheses(exp_type)
    if not body.hypothesis:
        merged["_suggested_hypothesis"] = hyp
    if not body.null_hypothesis:
        merged["_suggested_null_hypothesis"] = null_h
    if not body.success_criteria:
        merged["_suggested_success_criteria"] = success
    if not body.failure_criteria:
        merged["_suggested_failure_criteria"] = failure

    checks.extend(
        [
            ExperimentValidationCheck(key="hypothesis", label="Hypothesis", value=body.hypothesis or hyp, status="ok"),
            ExperimentValidationCheck(
                key="null_hypothesis", label="Null hypothesis", value=body.null_hypothesis or null_h, status="ok"
            ),
            ExperimentValidationCheck(
                key="success_criteria", label="Success criteria", value=body.success_criteria or success, status="ok"
            ),
            ExperimentValidationCheck(
                key="failure_criteria", label="Failure criteria", value=body.failure_criteria or failure, status="ok"
            ),
        ]
    )

    if body.preset and not preset_allows_major_evidence(body.preset):
        limitations.append("Quick Check preset cannot produce major evidence.")

    meta = TEMPLATE_META.get(exp_type, {})
    if meta:
        for req in meta.get("required_fields", []):
            if req == "symbols" and symbol_count < min_symbols:
                continue
            if req == "factors" and (merged.get("factors") or merged.get("factor_ids")):
                continue
            if req in merged or req in (body.universe_definition or {}):
                continue
            if req == "symbol" and (merged.get("symbol") or symbols):
                continue
            if req in ("sleeve",) and body.sleeve:
                continue
            if req == "policy" and merged.get("policy"):
                continue

    has_errors = any(c.status == "error" for c in checks)
    can_run = not has_errors

    return ExperimentValidationResponse(
        valid=not has_errors,
        can_run=can_run,
        symbol_count=symbol_count,
        missing_data_rate=missing_data_rate,
        expected_periods=expected_periods,
        data_cutoff=str(data_cutoff),
        dependency_availability=dependencies,
        major_limitations=limitations,
        checks=checks,
        resolved_universe=symbols[:50],
        merged_parameters=merged,
    )
