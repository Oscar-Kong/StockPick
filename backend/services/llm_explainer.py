"""Generate structured stock analysis via LLM with strict guardrails."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
import re
from typing import Any

import requests

from config import (
    INVEST_ALLOWED_STRATEGIES,
    INVEST_AVOID_LIST,
    INVEST_INTERESTED_SECTORS,
    INVEST_MAX_POSITION_SIZE,
    INVEST_RISK_TOLERANCE,
    INVEST_TIME_HORIZON,
    LLM_API_KEY,
    LLM_BASE_URL,
    LLM_ENABLED,
    LLM_MODEL,
    LLM_REASONING_EFFORT,
    LLM_VERBOSITY,
)

logger = logging.getLogger(__name__)

# Banned directional language — post-generation filter
BANNED_PATTERNS = [
    r"\bbuy\b",
    r"\bsell\b",
    r"\bstrong buy\b",
    r"\bstrong sell\b",
    r"\brecommend\b",
    r"\btarget price\b",
    r"\bprice will\b",
    r"\bgoing to (rise|fall|go up|go down)\b",
    r"\bexpect.*(gain|loss|return)\b",
]

ANALYSIS_SECTIONS = [
    "data_freshness_check",
    "market_environment_summary",
    "watchlist",
    "top_analyses",
    "final_summary",
]

JSON_SCHEMA_HINT = {
    "ticker": "",
    "timestamp": "",
    "view": "bullish | bearish | neutral | insufficient_evidence",
    "status": "reject | monitor | research_further | paper_trade_candidate",
    "supporting_evidence": [],
    "counterarguments": [],
    "primary_catalyst": "",
    "invalidation_condition": "",
    "missing_data": [],
    "risk_score": 1,
    "confidence_score": 1,
    "reasoning_summary": "",
}


def _investing_profile_block() -> str:
    interested = INVEST_INTERESTED_SECTORS or "not specified"
    avoid = INVEST_AVOID_LIST or "not specified"
    return f"""My investing profile:
- Account type: personal investing account
- Market: U.S. equities and ETFs
- Time horizon: {INVEST_TIME_HORIZON}
- Risk tolerance: {INVEST_RISK_TOLERANCE}
- Maximum position size: {INVEST_MAX_POSITION_SIZE}
- Strategies allowed: {INVEST_ALLOWED_STRATEGIES}
- Sectors I am interested in: {interested}
- Sectors or tickers I want to avoid: {avoid}
"""


def _analysis_system_prompt() -> str:
    return f"""You are my personal stock market research analyst. Your job is not to guarantee predictions or blindly recommend trades.
Your job is to analyze current market data, identify possible opportunities and risks, and produce a structured, evidence-based output for decision support.

{_investing_profile_block()}

Rules you must follow:
1. Use only current, verifiable information from provided structured inputs. State any timestamp fields used.
2. Never invent prices, financial metrics, catalysts, filings, news, earnings dates, or technical indicators.
3. If recent data is insufficient, explicitly say so and avoid directional conviction.
4. Separate facts from interpretation.
5. Do not give confident buy/sell calls based on momentum, hype, or social-media attention.
6. Always include bear case, invalidation, and what evidence would make the thesis wrong.
7. Prefer no-trade/watchlist when evidence is mixed.
8. Every candidate must be supported by concrete data fields.
9. Flag major upcoming risks when present in input data.
10. For any potential setup, explain what to confirm before acting.

Output format (single-symbol adapted):
A. Data freshness check
B. Market environment summary (if market-wide fields are missing, say so)
C. Watchlist table (for single symbol, use one-row watchlist snapshot)
D. Top detailed analysis (single ticker)
E. Final summary with one classification only:
Avoid / Watchlist only / Research further / Paper-trade candidate / Potential position candidate pending my own confirmation

Important:
- You are not a financial adviser.
- Never output direct buy/sell language.
- If evidence is insufficient, say exactly:
"I do not have enough verified evidence to support a trade idea."
"""


REASONING_SYSTEM_PROMPT = """You are the reasoning layer of a personal stock research system.

You will receive structured numerical data from verified market-data APIs. Do not create new numerical facts. Only analyze provided fields.

Your task:
1. Identify whether the data supports bullish, bearish, neutral, or insufficient_evidence.
2. Explain strongest supporting evidence.
3. Explain strongest counterargument.
4. Identify primary catalyst.
5. Identify invalidation condition.
6. Rate risk 1-5.
7. Rate confidence 1-5.
8. Choose one status:
   - reject
   - monitor
   - research_further
   - paper_trade_candidate

Never output buy or sell.
Never infer missing values.
If important data is missing, lower confidence and list exact missing fields.
Return valid JSON only.
"""

REPORT_PROMPT_GUIDANCE = """Analyze [TICKER] as a possible personal investment over the selected time horizon.
Use current verified data only. Examine:
- current price and movement
- earnings, revenue growth, margins, guidance
- valuation vs own history and peers
- upcoming catalysts with dates
- verified news summaries
- relative strength vs S&P500 and sector
- downside risks
- bull/base/bear scenarios
- invalidation condition
Conclude with one classification only:
Avoid / Watchlist only / Research further / Paper-trade candidate / Potential position candidate pending my own confirmation.
"""


def _build_structured_payload(
    symbol: str,
    bucket: str,
    score: float,
    metrics: dict[str, Any],
    signals: list[dict] | None,
    valuation_warnings: list[str] | None,
    quant_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if quant_context:
        return quant_context
    clean_metrics = {
        k: v
        for k, v in metrics.items()
        if k in (
            "as_of",
            "price",
            "price_change_1d",
            "price_change_5d",
            "volume",
            "relative_volume",
            "ma20",
            "ma50",
            "ma200",
            "rsi",
            "volatility",
            "pe_ratio",
            "peg_ratio",
            "revenue_growth",
            "earnings_growth",
            "profit_margin",
            "roe",
            "beta",
            "sector",
            "market_cap",
            "earnings_date",
            "days_until_earnings",
            "news_score",
            "_reconcile_quality",
            "relative_strength",
        )
        and v is not None
    }
    signal_summary = [
        {
            "name": s.get("name"),
            "value": round(float(s.get("value", 0)), 2),
            "contribution": round(float(s.get("contribution", 0)), 2),
        }
        for s in (signals or [])[:8]
    ]
    return {
        "ticker": symbol,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "bucket": bucket,
        "quantitative_score": round(score, 2),
        "metrics": clean_metrics,
        "signal_scores": signal_summary,
        "valuation_flags": (valuation_warnings or [])[:5],
    }


def _contains_banned_language(text: str) -> bool:
    lower = text.lower()
    for pat in BANNED_PATTERNS:
        if re.search(pat, lower, re.IGNORECASE):
            return True
    return False


def _sanitize_output(text: str) -> str:
    lines = text.split("\n")
    cleaned = []
    for line in lines:
        if any(re.search(pat, line, re.IGNORECASE) for pat in BANNED_PATTERNS):
            continue
        cleaned.append(line)
    result = "\n".join(cleaned).strip()
    disclaimer = "This is objective data analysis for research only, not investment advice."
    if disclaimer.lower() not in result.lower():
        result = result + "\n\n" + disclaimer
    return result


def _validate_sections(text: str) -> bool:
    required_markers = ["data freshness", "market environment", "watchlist", "analysis", "final summary"]
    lower = text.lower()
    return sum(1 for marker in required_markers if marker in lower) >= 3


def _extract_json_object(text: str) -> dict[str, Any] | None:
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


def _call_llm(messages: list[dict[str, str]], max_tokens: int = 550, temperature: float = 0.2) -> str:
    url = f"{LLM_BASE_URL.rstrip('/')}/chat/completions"
    body: dict[str, Any] = {
        "model": LLM_MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if LLM_MODEL.startswith("gpt-5") or "o1" in LLM_MODEL or "o3" in LLM_MODEL:
        body["reasoning_effort"] = LLM_REASONING_EFFORT
        body["verbosity"] = LLM_VERBOSITY
    headers = {"Authorization": f"Bearer {LLM_API_KEY}", "Content-Type": "application/json"}
    response = requests.post(url, json=body, headers=headers, timeout=35)
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"].strip()


def _fallback_reasoning(symbol: str, payload: dict[str, Any]) -> dict[str, Any]:
    missing = []
    for key in ("price", "volume", "earnings_date", "revenue_growth", "pe_ratio"):
        if payload.get("metrics", {}).get(key) is None:
            missing.append(key)
    view = "insufficient_evidence" if missing else "neutral"
    return {
        "ticker": symbol,
        "timestamp": payload.get("timestamp", ""),
        "view": view,
        "status": "monitor" if view != "insufficient_evidence" else "research_further",
        "supporting_evidence": ["Rule-based quantitative score available from internal model."],
        "counterarguments": ["Several market fields are missing from current payload."],
        "primary_catalyst": payload.get("metrics", {}).get("earnings_date", "") or "No verified catalyst in payload",
        "invalidation_condition": "New verified data contradicts current momentum/fundamental signals.",
        "missing_data": missing,
        "risk_score": 3,
        "confidence_score": 2 if missing else 3,
        "reasoning_summary": "Fallback reasoning due to limited LLM output or missing fields.",
    }


def _fallback_sections(symbol: str, bucket: str, metrics: dict[str, Any], warnings: list[str] | None) -> dict[str, str]:
    return {
        "data_freshness_check": f"Ticker: {symbol}. Timestamp reflects current API response time. Missing fields may reduce confidence.",
        "market_environment_summary": "Market-wide regime fields are not fully available in this endpoint payload.",
        "watchlist": f"Single-symbol watchlist candidate: {symbol} ({bucket}). Main risk flags: {warnings or ['none']}.",
        "top_analyses": "Facts: derived from provided metrics only. Interpretation: limited due to available fields.",
        "final_summary": "Classification: Research further. Confirm fresh price/volume/catalyst fields before action.",
    }


def _fallback_explanation(
    symbol: str,
    bucket: str,
    score: float,
    summary: str,
    metrics: dict[str, Any],
    warnings: list[str] | None,
) -> str:
    sections = _fallback_sections(symbol, bucket, metrics, warnings)
    return "\n".join(
        [
            f"A. Data freshness check\n- {sections['data_freshness_check']}",
            f"B. Market environment summary\n- {sections['market_environment_summary']}",
            f"C. Watchlist table\n- {sections['watchlist']}",
            f"D. Top detailed analyses\n- {sections['top_analyses']}",
            "E. Final summary\n- Classification: Research further",
            f"- Internal quantitative score: {score:.1f}/100. {summary}",
            "I do not have enough verified evidence to support a trade idea."
            if score < 40
            else "This is objective data analysis for research only, not investment advice.",
        ]
    )


def _parse_sections(text: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    mapping = {
        "a. data freshness": "data_freshness_check",
        "b. market environment": "market_environment_summary",
        "c. watchlist": "watchlist",
        "d. top": "top_analyses",
        "e. final summary": "final_summary",
    }
    current: str | None = None
    for line in text.split("\n"):
        lower = line.lower().strip()
        hit = None
        for marker, key in mapping.items():
            if lower.startswith(marker):
                hit = key
                break
        if hit:
            current = hit
            sections[current] = line.strip()
            continue
        if current and line.strip():
            sections[current] = sections.get(current, "") + " " + line.strip()
    return sections


def generate_explanation(
    symbol: str,
    bucket: str,
    score: float,
    summary: str,
    metrics: dict[str, Any],
    signals: list[dict] | None = None,
    news_headlines: list[str] | None = None,
    valuation_warnings: list[str] | None = None,
    quant_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return structured analysis with source tag and reasoning payload."""
    payload = _build_structured_payload(
        symbol, bucket, score, metrics, signals, valuation_warnings, quant_context=quant_context
    )

    # When full quant context is supplied, delegate to report narrative (no new rating).
    if quant_context and quant_context.get("system_rating"):
        from services.report_narrative import generate_report_narrative

        narrative = generate_report_narrative(quant_context)
        rating = quant_context["system_rating"]
        text_parts = [
            narrative["executive_summary"],
            "",
            "What would change my mind?",
            *[f"- {x}" for x in narrative.get("what_would_change_my_mind", [])],
            "",
            "Data quality limitations",
            *[f"- {x}" for x in narrative.get("data_quality_limitations", [])],
            "",
            narrative.get("disclaimer", ""),
        ]
        return {
            "text": "\n".join(text_parts),
            "source": narrative.get("source", "rules"),
            "sections": {
                "executive_summary": narrative["executive_summary"],
                "what_would_change_my_mind": narrative.get("what_would_change_my_mind", []),
                "data_quality_limitations": narrative.get("data_quality_limitations", []),
                "final_summary": f"System rating: {rating.get('system_label')} ({rating.get('action')})",
            },
            "reasoning": {
                "system_rating": rating,
                "uncertainty": narrative.get("uncertainty", []),
            },
            "structured_input": payload,
        }

    if not LLM_API_KEY or not LLM_ENABLED:
        return {
            "text": _fallback_explanation(symbol, bucket, score, summary, metrics, valuation_warnings),
            "source": "rules",
            "sections": _fallback_sections(symbol, bucket, metrics, valuation_warnings),
            "reasoning": _fallback_reasoning(symbol, payload),
            "structured_input": payload,
        }

    reasoning_prompt = (
        "Analyze this single ticker payload. Return ONLY valid JSON in the required schema.\n\n"
        f"Schema template:\n{json.dumps(JSON_SCHEMA_HINT, indent=2)}\n\n"
        f"Input payload:\n{json.dumps(payload, indent=2)}"
    )

    try:
        reasoning_raw = _call_llm(
            [
                {"role": "system", "content": REASONING_SYSTEM_PROMPT},
                {"role": "user", "content": reasoning_prompt},
            ],
            max_tokens=420,
            temperature=0.1,
        )
        reasoning = _extract_json_object(reasoning_raw) or _fallback_reasoning(symbol, payload)
    except Exception as exc:
        logger.warning("Reasoning-layer call failed: %s", exc)
        reasoning = _fallback_reasoning(symbol, payload)

    narrative_user_prompt = (
        "Create a concise but structured analyst note in sections A-E, using ONLY the payload and reasoning JSON.\n"
        "Treat this as single-symbol mode (one-row watchlist).\n"
        "Never emit buy/sell language.\n"
        f"\nReport-style guidance:\n{REPORT_PROMPT_GUIDANCE}\n"
        f"\nStructured payload:\n{json.dumps(payload, indent=2)}\n"
        f"\nReasoning JSON:\n{json.dumps(reasoning, indent=2)}\n"
        f"\nVerified news summaries (optional):\n{json.dumps((news_headlines or [])[:5], indent=2)}\n"
    )

    try:
        raw = _call_llm(
            [
                {"role": "system", "content": _analysis_system_prompt()},
                {"role": "user", "content": narrative_user_prompt},
            ],
            max_tokens=850,
            temperature=0.2,
        )
        if _contains_banned_language(raw):
            raw = _sanitize_output(raw)
            if _contains_banned_language(raw):
                raise ValueError("Banned directional phrasing persisted after sanitize")
        if not _validate_sections(raw):
            raw = _fallback_explanation(symbol, bucket, score, summary, metrics, valuation_warnings)
        return {
            "text": _sanitize_output(raw),
            "source": "llm",
            "sections": _parse_sections(raw),
            "reasoning": reasoning,
            "structured_input": payload,
        }
    except Exception as exc:
        logger.warning("LLM explanation failed: %s", exc)
        return {
            "text": _fallback_explanation(symbol, bucket, score, summary, metrics, valuation_warnings),
            "source": "rules",
            "sections": _fallback_sections(symbol, bucket, metrics, valuation_warnings),
            "reasoning": reasoning,
            "structured_input": payload,
        }

