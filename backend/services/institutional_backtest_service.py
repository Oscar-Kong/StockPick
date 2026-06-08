"""Service layer for institutional portfolio backtest."""
from __future__ import annotations

from config import BACKTEST_INSTITUTIONAL
from engines.backtest.institutional import InstitutionalBacktestResult, run_institutional_policy_backtest
from models.schemas import PortfolioPolicyBacktestRequest, PortfolioPolicyBacktestResponse
from services.policy_backtest import PolicyBacktestResult, run_policy_backtest


def _to_response(
    result: PolicyBacktestResult | InstitutionalBacktestResult,
    *,
    symbols_requested: list[str],
    institutional: bool,
) -> PortfolioPolicyBacktestResponse:
    extra: dict = {}
    if isinstance(result, InstitutionalBacktestResult):
        extra = dict(
            sortino_ratio=result.sortino_ratio,
            calmar_ratio=result.calmar_ratio,
            beta=result.beta,
            alpha_vs_spy_pct=result.alpha_vs_spy_pct,
            total_cost_pct=result.total_cost_pct,
            total_cost_usd=result.total_cost_usd,
            run_id=result.run_id,
            cost_events=result.cost_events,
            institutional=True,
        )
    return PortfolioPolicyBacktestResponse(
        policy=result.policy,
        rebalance=result.rebalance,
        engine=getattr(result, "engine", "policy_sim"),
        lookback_period=result.lookback_period,
        symbols_requested=symbols_requested,
        symbols_used=result.symbols_used,
        excluded=result.excluded,
        initial_capital=result.initial_capital,
        final_capital=result.final_capital,
        total_return_pct=result.total_return_pct,
        annualized_return_pct=result.annualized_return_pct,
        max_drawdown_pct=result.max_drawdown_pct,
        volatility_pct=result.volatility_pct,
        sharpe_ratio=result.sharpe_ratio,
        benchmark_return_pct=result.benchmark_return_pct,
        turnover_pct=result.turnover_pct,
        rebalance_count=result.rebalance_count,
        equity_curve=result.equity_curve,
        weights_history=result.weights_history,
        notes=result.notes,
        institutional=institutional,
        **extra,
    )


def run_portfolio_backtest(body: PortfolioPolicyBacktestRequest) -> PortfolioPolicyBacktestResponse:
    use_inst = body.institutional or BACKTEST_INSTITUTIONAL
    symbols_req = [s.upper() for s in body.symbols]

    if use_inst:
        result = run_institutional_policy_backtest(
            body.symbols,
            policy=body.policy,
            rebalance=body.rebalance,
            top_n=body.top_n,
            lookback_period=body.lookback_period,
            initial_capital=body.initial_capital,
            max_weight=body.max_weight,
            cash_buffer=body.cash_buffer,
            sleeve=body.sleeve,
            fee_bps=body.fee_bps,
            slip_bps=body.slip_bps,
            use_universe_pit=body.use_universe_pit,
            persist=True,
        )
        resp = _to_response(result, symbols_requested=symbols_req, institutional=True)
        from engines.audit.logger import audit_log

        audit_log(
            "institutional_backtest",
            payload={
                "run_id": resp.run_id,
                "policy": body.policy,
                "symbols": symbols_req[:10],
                "total_return_pct": resp.total_return_pct,
            },
        )
        return resp

    result = run_policy_backtest(
        body.symbols,
        policy=body.policy,
        rebalance=body.rebalance,
        top_n=body.top_n,
        lookback_period=body.lookback_period,
        initial_capital=body.initial_capital,
        max_weight=body.max_weight,
        cash_buffer=body.cash_buffer,
    )
    return _to_response(result, symbols_requested=symbols_req, institutional=False)
