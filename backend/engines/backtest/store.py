"""Persist institutional backtest runs."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from data.db_engine import get_engine
from engines.backtest.institutional import InstitutionalBacktestResult
from engines.quant_models import BacktestEquityPoint, BacktestRun


def persist_backtest_run(result: InstitutionalBacktestResult) -> None:
    engine = get_engine()
    metrics = {
        "total_return_pct": result.total_return_pct,
        "annualized_return_pct": result.annualized_return_pct,
        "max_drawdown_pct": result.max_drawdown_pct,
        "sharpe_ratio": result.sharpe_ratio,
        "sortino_ratio": result.sortino_ratio,
        "calmar_ratio": result.calmar_ratio,
        "beta": result.beta,
        "alpha_vs_spy_pct": result.alpha_vs_spy_pct,
        "total_cost_pct": result.total_cost_pct,
        "benchmark_return_pct": result.benchmark_return_pct,
    }
    config = {
        "policy": result.policy,
        "rebalance": result.rebalance,
        "lookback_period": result.lookback_period,
        "symbols_used": result.symbols_used,
    }
    finished = datetime.now(timezone.utc).replace(tzinfo=None)
    with Session(engine) as session:
        session.add(
            BacktestRun(
                run_id=result.run_id,
                run_type="institutional_policy",
                config_json=json.dumps(config),
                metrics_json=json.dumps(metrics),
                started_at=finished,
                finished_at=finished,
            )
        )
        for row in result.equity_curve:
            session.add(
                BacktestEquityPoint(
                    run_id=result.run_id,
                    as_of_date=row["date"],
                    equity=float(row["equity"]),
                )
            )
        session.commit()
    from services.research_run_service import notify_run_persisted

    notify_run_persisted(result.run_id, store="backtest_runs")
    from services.research_run_service import notify_run_persisted

    notify_run_persisted(result.run_id, store="backtest_runs")
