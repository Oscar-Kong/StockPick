"""Deterministic research run interpretation — verdict, reliability, optional LLM prose."""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from config import LLM_API_KEY, LLM_BASE_URL, LLM_ENABLED, LLM_MODEL
from models.schemas_research import (
    EvidenceImpact,
    MajorEvidenceGateResult,
    ResearchRunInterpretation,
    ResearchRunReliability,
    ResearchRunSummary,
    ResearchVerdict,
)
from services.major_evidence_gate import MIN_EFFECT_IC, evaluate_major_evidence_gate
from services.research_json import json_dumps, json_loads

logger = logging.getLogger(__name__)

MIN_RELIABLE_SAMPLE = 30


def compute_reliability(
    summary: ResearchRunSummary,
    detail: dict[str, Any],
    gate: MajorEvidenceGateResult,
) -> ResearchRunReliability:
    reasons: list[str] = []
    score = 50

    if summary.status in ("failed", "cancelled"):
        return ResearchRunReliability(score=0, status="invalid", reasons=["run_failed"])

    if gate.blocking_checks:
        return ResearchRunReliability(
            score=10,
            status="integrity_blocked",
            reasons=gate.blocking_checks[:5],
        )

    sample = summary.sample_size or detail.get("sample_size") or detail.get("periods_scored")
    if sample is None or int(sample) < 5:
        reasons.append("very_small_sample")
        score -= 25
    elif int(sample) < MIN_RELIABLE_SAMPLE:
        reasons.append("below_preferred_sample_size")
        score -= 10
    else:
        reasons.append("adequate_sample_size")
        score += 15

    passed = len(gate.passed_checks)
    failed = len(gate.failed_checks)
    if passed:
        score += min(25, passed * 4)
        reasons.append(f"gate_passed_{passed}")
    if failed:
        score -= min(30, failed * 5)
        reasons.append(f"gate_failed_{failed}")

    if summary.warnings:
        score -= min(15, len(summary.warnings) * 3)
        reasons.append("warnings_present")

    score = max(0, min(100, score))
    if score >= 70:
        status = "high"
    elif score >= 45:
        status = "moderate"
    elif score >= 20:
        status = "low"
    else:
        status = "insufficient_data"
    return ResearchRunReliability(score=score, status=status, reasons=reasons)


def _metric_float(summary: ResearchRunSummary, detail: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        val = detail.get(key)
        if val is not None:
            try:
                return float(val)
            except (TypeError, ValueError):
                pass
    agg = detail.get("aggregate_horizons") or {}
    for stats in agg.values():
        if isinstance(stats, dict):
            for key in keys:
                if stats.get(key) is not None:
                    try:
                        return float(stats[key])
                    except (TypeError, ValueError):
                        pass
    for m in summary.primary_metrics:
        label = str(m.label).lower()
        if any(k.replace("_", " ") in label for k in keys):
            try:
                return float(m.value)
            except (TypeError, ValueError):
                pass
    return None


def compute_verdict(
    summary: ResearchRunSummary,
    detail: dict[str, Any],
    gate: MajorEvidenceGateResult,
    reliability: ResearchRunReliability,
) -> ResearchVerdict:
    if summary.status in ("failed", "cancelled") or gate.blocking_checks:
        return "invalid"
    if summary.blockers and any("job_failed" in b or "explicit_blocker" in b for b in summary.blockers):
        return "invalid"

    sample = summary.sample_size or detail.get("sample_size") or detail.get("periods_scored") or 0
    if int(sample or 0) < 1 and summary.run_type not in ("quant_job",):
        return "insufficient_data"
    if reliability.status == "insufficient_data" and int(sample or 0) < 5:
        return "insufficient_data"

    run_type = summary.run_type
    if run_type == "walk_forward":
        mean_ic = _metric_float(summary, detail, "mean_rank_ic")
        if mean_ic is None:
            return "insufficient_data"
        if mean_ic >= MIN_EFFECT_IC:
            return "supports_hypothesis"
        if mean_ic <= -MIN_EFFECT_IC:
            return "rejects_hypothesis"
        return "inconclusive"

    if run_type == "factor_ic_panel":
        mean_ic = _metric_float(summary, detail, "mean_ic")
        if mean_ic is None:
            return "insufficient_data"
        if mean_ic >= MIN_EFFECT_IC:
            return "supports_hypothesis"
        if mean_ic <= -MIN_EFFECT_IC:
            return "rejects_hypothesis"
        return "inconclusive"

    if run_type == "pairs":
        coint = int(detail.get("cointegrated_count") or summary.sample_size or 0)
        if coint >= 1:
            return "supports_hypothesis"
        if int(detail.get("pairs_returned") or 0) == 0:
            return "insufficient_data"
        return "inconclusive"

    if run_type == "prediction_outcomes":
        outcomes = int(detail.get("outcomes_count") or summary.sample_size or 0)
        if outcomes < 5:
            return "insufficient_data"
        err = _metric_float(summary, detail, "mean_prediction_error_pct")
        if err is None:
            return "inconclusive"
        if abs(err) <= 5.0:
            return "supports_hypothesis"
        if abs(err) >= 15.0:
            return "rejects_hypothesis"
        return "inconclusive"

    if run_type == "similar_signal":
        sample_n = int(detail.get("sample_n") or summary.sample_size or 0)
        if sample_n < 10:
            return "insufficient_data"
        avg = _metric_float(summary, detail, "avg_forward_return_pct")
        if avg is None:
            return "inconclusive"
        if avg >= 2.0:
            return "supports_hypothesis"
        if avg <= -2.0:
            return "rejects_hypothesis"
        return "inconclusive"

    if run_type == "portfolio_policy":
        ret = _metric_float(summary, detail, "total_return_pct")
        if ret is None:
            return "inconclusive"
        if ret >= 5.0:
            return "supports_hypothesis"
        if ret <= -5.0:
            return "rejects_hypothesis"
        return "inconclusive"

    if run_type == "quant_job":
        if summary.status == "completed":
            return "inconclusive"
        return "invalid"

    return "inconclusive"


def _deterministic_conclusion(
    verdict: ResearchVerdict,
    summary: ResearchRunSummary,
    detail: dict[str, Any],
) -> str:
    name = summary.name or summary.run_id
    templates = {
        "supports_hypothesis": f"{name} provides measurable support for the stated hypothesis under current model versions.",
        "rejects_hypothesis": f"{name} shows evidence against the stated hypothesis within the tested window.",
        "inconclusive": f"{name} does not provide a clear directional conclusion — signals are mixed or weak.",
        "insufficient_data": f"{name} lacks enough trustworthy observations to support a directional verdict.",
        "invalid": f"{name} cannot be interpreted because the run failed integrity checks or did not complete.",
    }
    return templates.get(verdict, templates["inconclusive"])


def _supporting_observations(
    summary: ResearchRunSummary,
    detail: dict[str, Any],
    gate: MajorEvidenceGateResult,
) -> list[str]:
    obs: list[str] = []
    for m in summary.primary_metrics[:2]:
        obs.append(f"{m.label}: {m.value}")
    for check in gate.passed_checks[:2]:
        obs.append(f"Gate passed: {check.replace('_', ' ')}")
    if not obs and summary.sample_size:
        obs.append(f"Sample size recorded: {summary.sample_size}")
    return obs[:3]


def _main_limitation(summary: ResearchRunSummary, gate: MajorEvidenceGateResult) -> str:
    if gate.blocking_checks:
        return gate.blocking_checks[0].replace("_", " ")
    if gate.failed_checks:
        return f"Major evidence gate failed: {gate.failed_checks[0].replace('_', ' ')}"
    if summary.warnings:
        return summary.warnings[0].replace("_", " ")
    return "Standard research limitations apply — results are sleeve- and window-specific."


def _suggested_next_action(verdict: ResearchVerdict, summary: ResearchRunSummary) -> str:
    actions = {
        "supports_hypothesis": "Replicate with robust_validation preset and compare against an adjacent date window.",
        "rejects_hypothesis": "Archive hypothesis or refine universe/parameters before another full run.",
        "inconclusive": "Extend the data window or increase sample size, then re-run with standard_research preset.",
        "insufficient_data": "Wait for more resolved outcomes or widen universe before interpreting.",
        "invalid": "Fix blockers noted in warnings, then launch a fresh experiment from the studio.",
    }
    if summary.experiment_id:
        return actions.get(verdict, actions["inconclusive"])
    return actions.get(verdict, actions["inconclusive"]) + " Link an experiment to track follow-ups."


def build_interpretation(
    summary: ResearchRunSummary,
    detail: dict[str, Any],
    *,
    use_llm: bool | None = None,
) -> ResearchRunInterpretation:
    gate = evaluate_major_evidence_gate(
        run_type=summary.run_type,
        summary=detail,
        parameters=summary.parameters,
        warnings=summary.warnings,
        blockers=summary.blockers,
    )
    reliability = compute_reliability(summary, detail, gate)
    verdict = compute_verdict(summary, detail, gate, reliability)
    conclusion = _deterministic_conclusion(verdict, summary, detail)

    interpretation = ResearchRunInterpretation(
        verdict=verdict,
        conclusion=conclusion,
        evidence_impact=summary.evidence_impact,
        reliability=reliability,
        supporting_observations=_supporting_observations(summary, detail, gate),
        main_limitation=_main_limitation(summary, gate),
        suggested_next_action=_suggested_next_action(verdict, summary),
        major_evidence_gate=gate,
    )

    if use_llm is None:
        use_llm = bool(LLM_ENABLED and LLM_API_KEY)
    if use_llm:
        prose = _optional_llm_prose(interpretation, summary, detail)
        if prose:
            interpretation.prose = prose
    return interpretation


def _optional_llm_prose(
    interpretation: ResearchRunInterpretation,
    summary: ResearchRunSummary,
    detail: dict[str, Any],
) -> str | None:
    """Rewrite prose only — never change verdict, impact, reliability, or metrics."""
    if not LLM_API_KEY or not LLM_ENABLED:
        return None
    try:
        import urllib.request

        payload = {
            "model": LLM_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Rewrite the research conclusion in clearer prose. "
                        "Do NOT change verdict, evidence impact, reliability score, numeric values, "
                        "warnings, or suggested next action. Return plain text only."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "verdict": interpretation.verdict,
                            "conclusion": interpretation.conclusion,
                            "evidence_impact": interpretation.evidence_impact,
                            "reliability": interpretation.reliability.model_dump(),
                            "observations": interpretation.supporting_observations,
                            "limitation": interpretation.main_limitation,
                            "next_action": interpretation.suggested_next_action,
                            "run_type": summary.run_type,
                            "metrics": [m.model_dump() for m in summary.primary_metrics],
                        }
                    ),
                },
            ],
            "temperature": 0.2,
        }
        req = urllib.request.Request(
            f"{LLM_BASE_URL.rstrip('/')}/chat/completions",
            data=json.dumps(payload).encode(),
            headers={"Authorization": f"Bearer {LLM_API_KEY}", "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read().decode())
        text = (body.get("choices") or [{}])[0].get("message", {}).get("content", "")
        text = str(text).strip()
        if not text:
            return None
        if interpretation.verdict not in text:
            return text[:1200]
        return text[:1200]
    except Exception as exc:
        logger.debug("interpretation LLM skipped: %s", exc)
        return None


def parse_stored_interpretation(raw: str | None) -> ResearchRunInterpretation | None:
    if not raw:
        return None
    try:
        data = json_loads(raw, None)
        if isinstance(data, dict):
            return ResearchRunInterpretation.model_validate(data)
    except Exception:
        return None
    return None


def persist_interpretation(run_id: str, interpretation: ResearchRunInterpretation) -> None:
    from data.db_engine import get_engine
    from engines.quant_models import ResearchRunIndex
    from sqlalchemy.orm import Session

    engine = get_engine()
    with Session(engine) as session:
        row = session.get(ResearchRunIndex, run_id)
        if not row:
            return
        row.interpretation_json = json_dumps(interpretation.model_dump(mode="json"))
        row.verdict = interpretation.verdict
        row.evidence_impact = interpretation.evidence_impact
        row.reliability_json = json_dumps(interpretation.reliability.model_dump())
        session.commit()


def sanitize_llm_prose(prose: str, interpretation: ResearchRunInterpretation) -> str:
    """Strip attempts to override authoritative fields in malformed LLM output."""
    cleaned = prose
    for pattern in (
        r"verdict\s*[:=]\s*\w+",
        r"evidence_impact\s*[:=]\s*\w+",
        r"reliability\s*[:=]\s*\d+",
    ):
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip() or interpretation.conclusion
