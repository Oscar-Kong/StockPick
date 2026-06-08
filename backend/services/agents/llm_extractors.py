"""Optional LLM structured extraction for specialist agents."""
from __future__ import annotations

from services.agent_orchestrator import AgentOutput
from services.agents.structured import enrich_bear_case, enrich_fundamental, enrich_valuation


def enrich_agents_with_llm(agents: list[AgentOutput], symbol: str) -> list[dict]:
    """Augment select agents with LLM JSON — quant recommendation unchanged."""
    out: list[dict] = []
    for a in agents:
        signals = dict(a.signals)
        summary = a.summary
        if a.agent == "fundamental_analyst":
            extra = enrich_fundamental(symbol, signals)
            signals["llm"] = extra
            summary = extra.get("summary") or summary
        elif a.agent == "valuation":
            extra = enrich_valuation(symbol, signals)
            signals["llm"] = extra
            summary = extra.get("summary") or summary
        elif a.agent == "bear_case":
            extra = enrich_bear_case(symbol, summary)
            if extra.get("risks"):
                signals["llm_risks"] = extra["risks"]
            summary = extra.get("summary") or summary
        out.append(
            {"agent": a.agent, "signals": signals, "summary": summary, "confidence": a.confidence}
        )
    return out
