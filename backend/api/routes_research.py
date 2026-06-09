"""Walk-forward research API — offline scoring evaluation, no live weight updates."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from models.schemas_v2 import (
    PairsResearchRequest,
    PairsResearchResponse,
    QuantLabLastRunSummary,
    WalkForwardResearchRequest,
    WalkForwardResearchResponse,
    WalkForwardRunDetailResponse,
)
from services.walk_forward_research_service import (
    WalkForwardConfig,
    load_walk_forward_run,
    run_walk_forward_research,
)
from services.pairs_research_service import run_pairs_research
from services.quant_lab_summary_service import build_pairs_last_run, build_walk_forward_last_run

router = APIRouter(prefix="/research", tags=["research"])


@router.post("/walk-forward", response_model=WalkForwardResearchResponse)
def post_walk_forward_research(body: WalkForwardResearchRequest):
    """Run unified walk-forward research for a sleeve over a date range."""
    try:
        cfg = WalkForwardConfig(
            sleeve=body.sleeve,
            start_date=body.start_date,
            end_date=body.end_date,
            rebalance_frequency=body.rebalance_frequency,
            forward_horizons=list(body.forward_horizons),
            max_symbols=body.max_symbols,
            persist_snapshots=body.persist_snapshots,
        )
        summary = run_walk_forward_research(cfg)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"walk-forward research failed: {exc}") from exc
    return summary


@router.get("/walk-forward/latest", response_model=QuantLabLastRunSummary)
def get_walk_forward_latest(sleeve: str = "medium"):
    """Latest persisted walk-forward run summary for a sleeve (read-only)."""
    return build_walk_forward_last_run(sleeve)


@router.get("/walk-forward/{run_id}", response_model=WalkForwardRunDetailResponse)
def get_walk_forward_run(run_id: str):
    """Load persisted walk-forward run metadata and JSON summary."""
    row = load_walk_forward_run(run_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"walk-forward run not found: {run_id}")
    return row


@router.post("/pairs", response_model=PairsResearchResponse)
def post_pairs_research(body: PairsResearchRequest):
    """Pairs-trading research: cointegration, hedge ratio, spread z-score (not auto-trade)."""
    try:
        return run_pairs_research(
            body.symbols,
            lookback_period=body.lookback_period,
            zscore_window=body.zscore_window,
            max_pairs=body.max_pairs,
            p_value_threshold=body.p_value_threshold,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"pairs research failed: {exc}") from exc


@router.get("/pairs/latest", response_model=QuantLabLastRunSummary)
def get_pairs_latest():
    """Latest pairs research summary — unavailable until runs are persisted."""
    return build_pairs_last_run()

