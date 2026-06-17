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
    PortfolioSummaryResponse,
    RebalancePreviewRequest,
    RebalancePreviewResponse,
)
from services.portfolio_optimizer import optimize_portfolio
from services.institutional_backtest_service import run_portfolio_backtest
from services.factor_exposure_service import build_factor_exposure_report
from services.portfolio_decision_service import run_portfolio_daily_decision
from services.portfolio_summary_service import build_portfolio_summary
from services.rebalance_service import compute_rebalance_preview
from utils.api_errors import portfolio_error
from utils.demo_guard import enforce_backtest_symbols, require_non_demo_mode
from config import DEMO_MODE

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.get("/summary", response_model=PortfolioSummaryResponse)
def portfolio_summary():
    """Canonical portfolio summary from the same ledger as Home."""
    try:
        return PortfolioSummaryResponse(**build_portfolio_summary(include_freshness=True))
    except Exception as exc:
        raise portfolio_error(
            code="PORTFOLIO_SUMMARY_FAILED",
            message="Could not load portfolio summary.",
            status_code=500,
            retryable=True,
            log_detail=str(exc),
        ) from exc


@router.post("/rebalance-preview", response_model=RebalancePreviewResponse)
def portfolio_rebalance_preview(body: RebalancePreviewRequest):
    """Trade preview from current holdings and target weights."""
    try:
        holdings = [h.model_dump() for h in body.holdings]
        result = compute_rebalance_preview(
            holdings=holdings,
            target_weights=body.target_weights,
            cash=body.cash,
            cash_reserve=body.cash_reserve,
            min_trade_amount=body.min_trade_amount,
            fractional_shares=body.fractional_shares,
            fee_bps=body.fee_bps,
            slippage_bps=body.slippage_bps,
            max_turnover=body.max_turnover,
        )
        return RebalancePreviewResponse(**result)
    except ValueError as exc:
        raise portfolio_error(
            code="REBALANCE_VALIDATION_FAILED",
            message=str(exc),
            status_code=400,
            retryable=False,
        ) from exc
    except Exception as exc:
        raise portfolio_error(
            code="REBALANCE_PREVIEW_FAILED",
            message="Could not compute rebalance preview.",
            status_code=500,
            retryable=True,
            log_detail=str(exc),
        ) from exc


@router.post("/optimize", response_model=PortfolioOptimizeResponse)
def portfolio_optimize(body: PortfolioOptimizeRequest):
    enforce_backtest_symbols(list(body.symbols))
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
        raise portfolio_error(
            code="PORTFOLIO_OPTIMIZATION_VALIDATION",
            message=str(exc),
            status_code=400,
            retryable=False,
        ) from exc
    except Exception as exc:
        raise portfolio_error(
            code="PORTFOLIO_OPTIMIZATION_FAILED",
            message="The allocation could not be calculated.",
            status_code=500,
            retryable=True,
            log_detail=str(exc),
        ) from exc

    notes = list(result.notes or [])
    notes.append("Long-only optimization is enforced.")

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
            "target_return": body.target_return,
            "lookback_period": body.lookback_period,
        },
        notes=notes,
    )


@router.post("/policy-backtest", response_model=PortfolioPolicyBacktestResponse)
def portfolio_policy_backtest(body: PortfolioPolicyBacktestRequest):
    enforce_backtest_symbols(list(body.symbols))
    try:
        return run_portfolio_backtest(body)
    except ValueError as exc:
        raise portfolio_error(
            code="POLICY_BACKTEST_VALIDATION",
            message=str(exc),
            status_code=400,
            retryable=False,
        ) from exc
    except Exception as exc:
        raise portfolio_error(
            code="POLICY_BACKTEST_FAILED",
            message="Policy backtest could not be completed.",
            status_code=500,
            retryable=True,
            log_detail=str(exc),
        ) from exc


@router.post("/factor-exposure", response_model=FactorExposureResponse)
def portfolio_factor_exposure(body: FactorExposureRequest):
    """Portfolio diagnostics: betas, rolling correlation, PCA loadings (not trade advice)."""
    enforce_backtest_symbols(list(body.symbols))
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
        raise portfolio_error(
            code="FACTOR_EXPOSURE_VALIDATION",
            message=str(exc),
            status_code=400,
            retryable=False,
        ) from exc
    except Exception as exc:
        raise portfolio_error(
            code="FACTOR_EXPOSURE_FAILED",
            message="Factor exposure analysis could not be completed.",
            status_code=500,
            retryable=True,
            log_detail=str(exc),
        ) from exc


@router.post("/daily-decision", response_model=PortfolioDecisionResponse)
def portfolio_daily_decision(body: PortfolioDecisionRequest):
    """Rule-based daily buy/keep/trim/sell guidance for manual holdings (not financial advice)."""
    if DEMO_MODE:
        body = body.model_copy(update={"persist": False})
    try:
        return run_portfolio_daily_decision(body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Daily decision failed: {exc}") from exc
