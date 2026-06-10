"""Portfolio optimization API routes."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from models.schemas import (
    FactorExposureRequest,
    FactorExposureResponse,
    PortfolioDecisionRequest,
    PortfolioDecisionResponse,
    PortfolioOptimizeItem,
    PortfolioOptimizeRequest,
    PortfolioOptimizeResponse,
    PortfolioPolicyBacktestRequest,
    PortfolioPolicyBacktestResponse,
)
from services.portfolio_optimizer import optimize_portfolio
from services.institutional_backtest_service import run_portfolio_backtest
from services.factor_exposure_service import build_factor_exposure_report
from services.portfolio_decision_service import run_portfolio_daily_decision

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.post("/optimize", response_model=PortfolioOptimizeResponse)
def portfolio_optimize(body: PortfolioOptimizeRequest):
    try:
        result = optimize_portfolio(
            body.symbols,
            objective=body.objective,
            max_weight=body.max_weight,
            cash_buffer=body.cash_buffer,
            target_return=body.target_return,
            lookback_period=body.lookback_period,
            kelly_overlay=body.kelly_overlay or body.objective == "kelly",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Optimization failed: {exc}") from exc

    notes = result.notes or []
    if body.long_only:
        notes = notes + ["Long-only optimization is enforced."]

    return PortfolioOptimizeResponse(
        objective=body.objective,
        optimizer=result.optimizer,
        symbols_requested=[s.upper() for s in body.symbols],
        symbols_used=result.symbols_used,
        excluded=result.excluded,
        weights=[
            PortfolioOptimizeItem(
                symbol=s,
                weight=w,
            )
            for s, w in sorted(result.weights.items(), key=lambda kv: kv[1], reverse=True)
        ],
        expected_return=result.expected_return,
        expected_volatility=result.expected_volatility,
        expected_sharpe=result.expected_sharpe,
        constraints={
            "max_weight": body.max_weight,
            "cash_buffer": body.cash_buffer,
            "long_only": body.long_only,
            "target_return": body.target_return,
            "lookback_period": body.lookback_period,
        },
        notes=notes,
    )


@router.post("/policy-backtest", response_model=PortfolioPolicyBacktestResponse)
def portfolio_policy_backtest(body: PortfolioPolicyBacktestRequest):
    try:
        return run_portfolio_backtest(body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Policy backtest failed: {exc}") from exc


@router.post("/factor-exposure", response_model=FactorExposureResponse)
def portfolio_factor_exposure(body: FactorExposureRequest):
    """Portfolio diagnostics: betas, rolling correlation, PCA loadings (not trade advice)."""
    try:
        return build_factor_exposure_report(
            body.symbols,
            benchmark=body.benchmark,
            lookback_period=body.lookback_period,
            correlation_window=body.correlation_window,
            n_components=body.n_components,
            pc1_concentration_threshold=body.pc1_concentration_threshold,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Factor exposure analysis failed: {exc}") from exc


@router.post("/daily-decision", response_model=PortfolioDecisionResponse)
def portfolio_daily_decision(body: PortfolioDecisionRequest):
    """Rule-based daily buy/keep/trim/sell guidance for manual holdings (not financial advice)."""
    try:
        return run_portfolio_daily_decision(body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Daily decision failed: {exc}") from exc

