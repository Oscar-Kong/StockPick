"""LLM narrative for research reports — explains quant outputs, never overrides ratings."""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from config import LLM_ENABLED, LLM_API_KEY, LLM_MODEL

logger = logging.getLogger(__name__)

DISCLAIMER_FOOTER = (
    "Not financial advice. This report explains quantitative system outputs for research "
    "workflows only. It does not constitute a recommendation to buy, sell, or hold any security."
)

NARRATIVE_JSON_HINT = {
    "executive_summary": "Explain the system rating in plain language — do not assign a new rating.",
    "investment_thesis": {
        "bull_case": "Supporting evidence from structured inputs only.",
        "bear_case": "Counter-evidence and risks from structured inputs only.",
        "edge": "What the quant system sees as differentiated — not a trade call.",
    },
    "uncertainty": ["List specific unknowns or mixed signals"],
    "what_would_change_my_mind": ["Concrete evidence that would change the system view"],
    "data_quality_limitations": ["Missing, stale, or low-confidence data issues"],
}

REPORT_NARRATIVE_SYSTEM = """You are a quantitative research explainer for a stock analysis platform.

Your job is to EXPLAIN outputs from a deterministic scoring and recommendation engine.
You must NOT invent a new rating, conviction score, or buy/sell/hold recommendation.

Rules:
1. The system_rating object is authoritative — explain it; never contradict or replace it.
2. Use ONLY facts present in the structured quant context. Do not invent prices, dates, or metrics.
3. Separate verified data from interpretation.
4. List uncertainty explicitly when signals conflict or data is thin.
5. "what_would_change_my_mind" must cite measurable changes (e.g. factor scores, risk items, valuation).
6. "data_quality_limitations" must reference reconcile flags, data confidence, missing fields.
7. Never use direct buy/sell language beyond restating the system label (e.g. "system label: watch").
8. Return valid JSON matching the template exactly — no markdown fences.

You are not a financial adviser."""


def _extract_json(text: str) -> dict[str, Any] | None:
    candidate = text.strip()
    try:
        return json.loads(candidate)
    except Exception:
        pass
    match = re.search(r"\{.*\}", candidate, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except Exception:
        return None


def _fallback_narrative(context: dict[str, Any]) -> dict[str, Any]:
    rating = context.get("system_rating") or {}
    label = rating.get("system_label", "unavailable")
    score = rating.get("composite_score", 0)
    attr = context.get("score_attribution") or {}
    risk = context.get("risk_breakdown") or {}
    dq = context.get("data_quality") or {}

    limitations: list[str] = []
    q = dq.get("reconcile_quality_score")
    if q is not None and q < 70:
        limitations.append(f"Reconcile data quality score is {q:.0f}/100 — cross-source verification is limited.")
    for flag in dq.get("reconcile_flags") or []:
        limitations.append(str(flag))
    if not limitations:
        limitations.append("Standard provider snapshot; no additional limitations flagged by reconcile.")

    change_mind: list[str] = []
    if risk.get("deduction_pts"):
        change_mind.append(f"Risk deduction falls below {risk['deduction_pts']:.0f} pts with clearer event visibility.")
    change_mind.append("Material improvement in top-weight factor scores on next rebalance.")
    change_mind.append("Valuation summary shifts from expensive to fair/cheap on verified fundamentals refresh.")

    top_factors = context.get("factor_contributions") or []
    factor_names = ", ".join(f.get("display_name", f.get("factor_id", "")) for f in top_factors[:3])

    risk_items = risk.get("items") or []
    bear_parts = []
    for item in risk_items[:3]:
        if isinstance(item, dict):
            bear_parts.append(str(item.get("detail") or item.get("category") or item))
        else:
            bear_parts.append(str(item))

    return {
        "executive_summary": (
            f"The quant system assigns {label.replace('_', ' ')} with composite score {score:.0f}/100 "
            f"(conviction {rating.get('conviction', 0):.0f}). "
            f"Raw score {attr.get('raw_score', 'n/a')} adjusted by regime, data quality, and risk deductions. "
            f"Top factors: {factor_names or 'n/a'}."
        ),
        "investment_thesis": {
            "bull_case": context.get("summary") or "See positive factor contributions in quantitative_analysis.",
            "bear_case": "; ".join(bear_parts) or "Elevated risk score or weak factors may cap upside.",
            "edge": f"Regime: {context.get('market_regime') or 'neutral'}; system sleeve {context.get('sleeve')}.",
        },
        "uncertainty": [
            "Rule-based narrative — enable LLM for richer explanation.",
            f"Diagnostics: {(context.get('diagnostics_summary') or {}).get('interpretation', 'not loaded')}",
        ],
        "what_would_change_my_mind": change_mind,
        "data_quality_limitations": limitations,
        "source": "rules",
    }


def generate_report_narrative(context: dict[str, Any]) -> dict[str, Any]:
    """
    Produce narrative sections explaining quant outputs.

    Never modifies system_rating. Returns dict with narrative fields + source tag.
    """
    if not LLM_ENABLED or not LLM_API_KEY:
        out = _fallback_narrative(context)
        out["disclaimer"] = DISCLAIMER_FOOTER
        return out

    user_prompt = (
        "Explain the following quant context for a research report.\n"
        "Do NOT create a new rating. The system_rating is fixed.\n\n"
        f"JSON template:\n{json.dumps(NARRATIVE_JSON_HINT, indent=2)}\n\n"
        f"Quant context:\n{json.dumps(context, indent=2, default=str)}\n"
    )

    try:
        from services.llm_explainer import _call_llm

        raw = _call_llm(
            [
                {"role": "system", "content": REPORT_NARRATIVE_SYSTEM},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=900,
            temperature=0.15,
        )
        parsed = _extract_json(raw)
        if not parsed:
            raise ValueError("LLM did not return valid JSON")

        out = {
            "executive_summary": str(parsed.get("executive_summary") or "")[:2000],
            "investment_thesis": {
                "bull_case": str((parsed.get("investment_thesis") or {}).get("bull_case", "")),
                "bear_case": str((parsed.get("investment_thesis") or {}).get("bear_case", "")),
                "edge": str((parsed.get("investment_thesis") or {}).get("edge", "")),
            },
            "uncertainty": list(parsed.get("uncertainty") or [])[:8],
            "what_would_change_my_mind": list(parsed.get("what_would_change_my_mind") or [])[:8],
            "data_quality_limitations": list(parsed.get("data_quality_limitations") or [])[:8],
            "source": "llm",
            "llm_model": LLM_MODEL,
        }
        out["disclaimer"] = DISCLAIMER_FOOTER
        return out
    except Exception as exc:
        logger.warning("Report narrative LLM failed: %s", exc)
        out = _fallback_narrative(context)
        out["disclaimer"] = DISCLAIMER_FOOTER
        return out
