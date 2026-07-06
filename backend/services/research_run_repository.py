"""Deep read module for Quant Lab Evidence runs."""
from __future__ import annotations

from models.schemas_research import (
    ResearchRunCompareDetailResponse,
    ResearchRunCompareResponse,
    ResearchRunDetailResponse,
    ResearchRunListResponse,
    ResearchRunSummary,
)
from services.research_run_detail_service import get_run_detail, load_detail_payload
from services.research_run_interpretation_service import build_interpretation
from services.research_run_service import (
    compare_runs,
    compare_runs_detail,
    get_run,
    list_runs,
    refresh_run_from_store,
)


def get_summary(run_id: str) -> ResearchRunSummary | None:
    return get_run(run_id)


def list_index(**kwargs) -> ResearchRunListResponse:
    return list_runs(**kwargs)


def get_detail(run_id: str, *, refresh: bool = False, use_llm: bool | None = None) -> ResearchRunDetailResponse | None:
    return get_run_detail(run_id, refresh=refresh, use_llm=use_llm)


def compare(run_ids: list[str]) -> ResearchRunCompareResponse:
    return compare_runs(run_ids)


def compare_detail(run_ids: list[str]) -> ResearchRunCompareDetailResponse:
    return compare_runs_detail(run_ids)


def refresh(run_id: str, store: str | None = None):
    return refresh_run_from_store(run_id, store)


def load_payload(summary: ResearchRunSummary) -> dict:
    return load_detail_payload(summary)


def interpret(summary: ResearchRunSummary, detail: dict, *, use_llm: bool | None = None):
    return build_interpretation(summary, detail, use_llm=use_llm)
