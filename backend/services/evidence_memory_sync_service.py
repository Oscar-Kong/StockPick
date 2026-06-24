"""Sync symbol-specific findings to Evidence Memory and resolve later outcomes."""
from __future__ import annotations

from typing import Any

from models.schemas_research import EvidenceMemoryCreate, EvidenceMemoryResponse, EvidenceMemoryUpdate
from services.evidence_memory_service import create_evidence_memory, list_evidence_memory, update_evidence_memory
from services.research_run_detail_service import load_detail_payload
from services.research_run_interpretation_service import build_interpretation
from services.research_run_service import get_run


def _finding_text(run_type: str, symbol: str, detail: dict[str, Any], interpretation_verdict: str) -> str:
    if run_type == "similar_signal":
        avg = detail.get("avg_forward_return_pct")
        return f"Similar-signal study for {symbol}: avg forward return {avg}% (verdict: {interpretation_verdict})"
    if run_type == "pairs":
        return f"Pairs research includes {symbol} in a cointegration screen (verdict: {interpretation_verdict})"
    return f"Research run flagged {symbol} (verdict: {interpretation_verdict})"


def sync_evidence_from_run(run_id: str) -> list[EvidenceMemoryResponse]:
    summary = get_run(run_id)
    if not summary:
        return []
    detail = load_detail_payload(summary)
    interpretation = build_interpretation(summary, detail, use_llm=False)
    created: list[EvidenceMemoryResponse] = []

    symbols: list[str] = []
    if summary.run_type == "similar_signal":
        sym = summary.parameters.get("symbol") or (summary.universe[0] if summary.universe else None)
        if sym:
            symbols.append(str(sym).upper())
    elif summary.run_type == "pairs":
        for pair in detail.get("pairs") or []:
            if isinstance(pair, dict):
                for s in pair.get("pair") or []:
                    symbols.append(str(s).upper())
        symbols = sorted(set(symbols))
    elif summary.universe:
        symbols = [str(s).upper() for s in summary.universe[:20]]

    if not symbols:
        return []

    existing = list_evidence_memory(run_id=run_id, limit=200)
    existing_symbols = {e.symbol for e in existing.items if e.symbol}

    for symbol in symbols:
        if symbol in existing_symbols:
            continue
        row = create_evidence_memory(
            EvidenceMemoryCreate(
                symbol=symbol,
                universe=summary.universe or None,
                experiment_id=summary.experiment_id,
                run_id=run_id,
                deterministic_finding=_finding_text(
                    summary.run_type, symbol, detail, interpretation.verdict
                ),
                verdict=interpretation.verdict,
                evidence_impact=interpretation.evidence_impact,
                reliability=interpretation.reliability.model_dump(),
                original_signal={"run_type": summary.run_type, "parameters": summary.parameters},
                factor_snapshot_ref={"sleeve": summary.sleeve, "data_cutoff": summary.data_cutoff},
                confirmation_status="pending",
            )
        )
        created.append(row)
    return created


def update_later_outcomes(run_id: str, outcomes: dict[str, Any]) -> list[EvidenceMemoryResponse]:
    """Attach forward outcomes without mutating original finding or signal."""
    items = list_evidence_memory(run_id=run_id, limit=200)
    updated: list[EvidenceMemoryResponse] = []
    for item in items.items:
        merged_outcomes = {**(item.forward_outcomes or {}), **outcomes}
        status = item.confirmation_status
        if outcomes.get("return_pct") is not None:
            ret = float(outcomes["return_pct"])
            orig = (item.original_signal or {}).get("expected_direction")
            if orig == "up" and ret > 0:
                status = "confirmed"
            elif orig == "up" and ret < 0:
                status = "contradicted"
            elif abs(ret) < 0.5:
                status = "inconclusive"
        row = update_evidence_memory(
            item.id,
            EvidenceMemoryUpdate(
                forward_outcomes=merged_outcomes,
                confirmation_status=status,
            ),
        )
        if row:
            updated.append(row)
    return updated


def resolve_outcomes_from_feedback(run_id: str) -> list[EvidenceMemoryResponse]:
    summary = get_run(run_id)
    if not summary or summary.run_type != "prediction_outcomes":
        return []
    try:
        from services.trade_feedback_service import feedback_summary

        fb = feedback_summary()
    except Exception:
        return []
    return update_later_outcomes(
        run_id,
        {
            "mean_prediction_error_pct": fb.get("mean_prediction_error_pct"),
            "outcomes_count": fb.get("outcomes_count"),
            "resolved_at": fb.get("latest_resolved_at"),
        },
    )
