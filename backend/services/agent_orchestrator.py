"""Multi-agent research pipeline — structured specialists feeding quant engine."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from config import LLM_ENABLED, LLM_AGENTS_ENABLED
from engines.data_confidence import build_data_confidence
from engines.earnings.revisions import build_earnings_setup
from engines.valuation.engine import evaluate_valuation

logger = logging.getLogger(__name__)


@dataclass
class AgentOutput:
    agent: str
    signals: dict[str, Any] = field(default_factory=dict)
    summary: str = ""
    confidence: float = 50.0


def data_auditor_agent(symbol: str, rec: Any | None = None) -> AgentOutput:
    dc = build_data_confidence(symbol, rec)
    return AgentOutput(
        agent="data_auditor",
        signals=dc.to_dict(),
        summary=f"Data confidence {dc.score:.0f}/100 with {len(dc.issues)} issues",
        confidence=dc.score,
    )


def fundamental_analyst_agent(info: dict[str, Any], fundamentals: dict[str, Any]) -> AgentOutput:
    rev_g = info.get("revenueGrowth")
    margin = fundamentals.get("operating_margin") or info.get("operatingMargins")
    roe = fundamentals.get("roe") or info.get("returnOnEquity")
    signals = {
        "revenue_growth": rev_g,
        "operating_margin": margin,
        "roe": roe,
        "debt_to_equity": fundamentals.get("debt_to_equity"),
    }
    score = 50.0
    if rev_g and float(rev_g) > 0.08:
        score += 15
    if roe and float(roe) > 0.15:
        score += 10
    return AgentOutput(
        agent="fundamental_analyst",
        signals=signals,
        summary="Fundamental quality assessed from reconciled metrics",
        confidence=min(100.0, score),
    )


def valuation_agent(info: dict[str, Any], fundamentals: dict[str, Any]) -> AgentOutput:
    val = evaluate_valuation(info, fundamentals)
    return AgentOutput(
        agent="valuation",
        signals=val.to_dict(),
        summary=f"Valuation verdict: {val.verdict.replace('_', ' ')}",
        confidence=val.valuation_score,
    )


def quant_factor_agent(factors: list[dict[str, Any]]) -> AgentOutput:
    return AgentOutput(
        agent="quant_factor",
        signals={"factors": factors},
        summary=f"{len(factors)} factor contributions computed",
        confidence=70.0,
    )


def earnings_agent(
    symbol: str,
    info: dict[str, Any],
    fundamentals: dict[str, Any],
    *,
    days_until_earnings: int | None = None,
    valuation_verdict: str | None = None,
) -> AgentOutput:
    setup = build_earnings_setup(
        symbol,
        info,
        fundamentals,
        days_until_earnings=days_until_earnings,
        valuation_verdict=valuation_verdict,
    )
    return AgentOutput(
        agent="earnings_catalyst",
        signals=setup.to_dict(),
        summary=setup.risk_note or "Earnings setup evaluated",
        confidence=setup.catalyst_score,
    )


def risk_agent(risk_assess: Any) -> AgentOutput:
    return AgentOutput(
        agent="risk",
        signals={
            "risk_score": getattr(risk_assess, "risk_score", None),
            "deduction_pts": getattr(risk_assess, "deduction_pts", None),
            "breakdown": getattr(risk_assess, "breakdown", []),
        },
        summary="Unified risk assessment",
        confidence=max(0.0, 100.0 - float(getattr(risk_assess, "risk_score", 50))),
    )


def bear_case_agent(
    *,
    valuation_verdict: str | None,
    risk_assess: Any,
    data_confidence: Any,
    similar_signal: dict[str, Any] | None = None,
) -> AgentOutput:
    risks: list[str] = []
    if valuation_verdict in ("expensive", "extremely_expensive"):
        risks.append("Valuation leaves little margin of safety")
    if getattr(risk_assess, "risk_score", 0) > 65:
        risks.append("Risk index elevated")
    if data_confidence.issues:
        risks.append(data_confidence.issues[0])
    if similar_signal and similar_signal.get("win_rate", 1) < 0.45:
        risks.append("Historical similar setups underperformed")
    summary = "; ".join(risks) if risks else "No dominant bear case identified"
    return AgentOutput(agent="bear_case", signals={"risks": risks}, summary=summary, confidence=60.0)


def final_judge_agent(recommendation: dict[str, Any]) -> AgentOutput:
    return AgentOutput(
        agent="final_judge",
        signals=recommendation,
        summary=f"Decision: {recommendation.get('recommendation', 'watch')}",
        confidence=float(recommendation.get("confidence", 50)),
    )


def run_agent_pipeline(
    *,
    symbol: str,
    info: dict[str, Any],
    fundamentals: dict[str, Any],
    factors: list[dict[str, Any]],
    risk_assess: Any,
    recommendation: dict[str, Any],
    rec: Any | None = None,
    days_until_earnings: int | None = None,
    similar_signal: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run all specialist agents; LLM optional for narrative enrichment only."""
    val = evaluate_valuation(info, fundamentals)
    dc = build_data_confidence(symbol, rec)

    agents = [
        data_auditor_agent(symbol, rec),
        fundamental_analyst_agent(info, fundamentals),
        valuation_agent(info, fundamentals),
        quant_factor_agent(factors),
        earnings_agent(
            symbol,
            info,
            fundamentals,
            days_until_earnings=days_until_earnings,
            valuation_verdict=val.verdict,
        ),
        risk_agent(risk_assess),
        bear_case_agent(
            valuation_verdict=val.verdict,
            risk_assess=risk_assess,
            data_confidence=dc,
            similar_signal=similar_signal,
        ),
        final_judge_agent(recommendation),
    ]

    payload = {
        "symbol": symbol.upper(),
        "agents": [
            {"agent": a.agent, "signals": a.signals, "summary": a.summary, "confidence": a.confidence}
            for a in agents
        ],
        "llm_enriched": False,
    }

    if LLM_ENABLED and LLM_AGENTS_ENABLED:
        try:
            from services.agents.llm_extractors import enrich_agents_with_llm

            payload["agents"] = enrich_agents_with_llm(agents, symbol)
            payload["llm_enriched"] = True
        except Exception as exc:
            logger.debug("LLM agent enrichment skipped: %s", exc)

    return payload


def _optional_llm_synthesis(agents: list[AgentOutput], symbol: str) -> str:
    summaries = [f"{a.agent}: {a.summary}" for a in agents if a.summary]
    return " | ".join(summaries[:4])
