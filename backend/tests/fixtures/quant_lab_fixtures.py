"""Deterministic Quant Lab fixtures — no live market data."""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from typing import Any

import numpy as np
import pandas as pd

from data.db_engine import get_engine
from engines.quant_models import (
    BacktestRun,
    FactorIcHistory,
    JobQueueItem,
    PairsResearchRun,
    PredictionOutcome,
    PredictionSnapshot,
)
from sqlalchemy.orm import Session

SYMBOLS_8 = ["AAA", "BBB", "CCC", "DDD", "EEE", "FFF", "GGG", "HHH"]
COINTEGRATED_PAIR = ("AAA", "BBB")
NON_COINTEGRATED_PAIR = ("CCC", "DDD")
STALE_SYMBOL = "STALE1"
MISSING_DATES_SYMBOL = "GAP1"
INSUFFICIENT_SYMBOL = "SHORT1"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def build_daily_ohlc(
    symbol: str,
    *,
    days: int = 520,
    start: str = "2022-01-03",
    base: float | None = None,
    drift: float = 0.0002,
    noise: float = 0.01,
    seed: int | None = None,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed or hash(symbol) % 2**31)
    dates = pd.bdate_range(start, periods=days)
    price = base if base is not None else 50.0 + (hash(symbol) % 20)
    rows = []
    for d in dates:
        price = max(1.0, price * (1.0 + drift + rng.normal(0, noise)))
        rows.append(
            {
                "date": d.date(),
                "open": price,
                "high": price * 1.01,
                "low": price * 0.99,
                "close": price,
                "volume": 1_000_000.0,
            }
        )
    return pd.DataFrame(rows)


def build_cointegrated_panel() -> pd.DataFrame:
    """AAA and BBB share a mean-reverting spread; others are independent."""
    n = 300
    dates = pd.bdate_range("2023-01-03", periods=n)
    rng = np.random.default_rng(42)
    common = np.cumsum(rng.normal(0, 0.5, n))
    aaa = 100 + common + rng.normal(0, 0.2, n)
    bbb = 50 + 0.8 * common + rng.normal(0, 0.2, n)
    series = {"AAA": aaa, "BBB": bbb}
    for sym in ["CCC", "DDD", "EEE", "FFF"]:
        series[sym] = 40 + np.cumsum(rng.normal(0.0001, 0.02, n))
    return pd.DataFrame(series, index=dates)


def build_price_panel_8_symbols() -> dict[str, pd.DataFrame]:
    panel: dict[str, pd.DataFrame] = {}
    for i, sym in enumerate(SYMBOLS_8):
        panel[sym] = build_daily_ohlc(sym, days=520, drift=0.0003 * (i + 1), seed=i + 1)
    panel[STALE_SYMBOL] = build_daily_ohlc(STALE_SYMBOL, days=520, start="2021-01-04", seed=99)
    panel[MISSING_DATES_SYMBOL] = build_daily_ohlc(MISSING_DATES_SYMBOL, days=400, seed=100).iloc[::2].reset_index(drop=True)
    panel[INSUFFICIENT_SYMBOL] = build_daily_ohlc(INSUFFICIENT_SYMBOL, days=30, seed=101)
    return panel


def seed_factor_ic(*, sleeve: str = "medium", as_of: date | None = None) -> date:
    as_of = as_of or date.today()
    engine = get_engine()
    with Session(engine) as session:
        for factor_id, ic in (("momentum", 0.08), ("quality", -0.02), ("value", 0.0)):
            session.add(
                FactorIcHistory(
                    factor_id=factor_id,
                    sleeve=sleeve,
                    as_of_date=as_of.isoformat(),
                    horizon_days=20,
                    ic=ic,
                    ir=ic * 2,
                    hit_rate=0.55 if ic and ic > 0 else 0.45,
                    sample_n=120,
                )
            )
        session.commit()
    return as_of


def seed_walk_forward_run(*, sleeve: str = "medium", run_id: str = "wf_test_001") -> str:
    summary = {
        "status": "completed",
        "sleeve": sleeve,
        "start_date": "2024-01-01",
        "end_date": "2024-06-30",
        "forward_horizons": [20],
        "periods_scored": 5,
        "rebalance_periods": 5,
        "aggregate_horizons": {"20": {"mean_rank_ic": 0.12, "mean_pearson_ic": 0.1}},
        "weights_updated": False,
    }
    config = {"sleeve": sleeve, "start_date": "2024-01-01", "end_date": "2024-06-30"}
    now = _utcnow()
    engine = get_engine()
    with Session(engine) as session:
        session.add(
            BacktestRun(
                run_id=run_id,
                run_type="walk_forward_research",
                config_json=json.dumps(config),
                metrics_json=json.dumps(summary),
                started_at=now - timedelta(hours=1),
                finished_at=now,
            )
        )
        session.commit()
    return run_id


def seed_predictions(*, resolved: int = 3, unresolved: int = 2) -> None:
    now = _utcnow()
    engine = get_engine()
    with Session(engine) as session:
        for i in range(resolved + unresolved):
            snap = PredictionSnapshot(
                symbol=f"SYM{i}",
                sleeve="medium",
                created_at=now - timedelta(days=30 - i),
                price=100.0 + i,
                recommendation="hold",
                confidence=0.7,
                time_horizon_days=20,
                alpha_score=60.0 + i,
                model_version="test_v1",
                source="v2_score",
                features_json="{}",
                thesis_json="{}",
            )
            session.add(snap)
            session.flush()
            if i < resolved:
                session.add(
                    PredictionOutcome(
                        prediction_id=snap.id,
                        return_20d=2.5 if i % 2 == 0 else -1.2,
                        resolved_at=now - timedelta(days=5),
                    )
                )
        session.commit()


def seed_pairs_run(*, run_id: str = "pairs_test_001") -> str:
    summary = {
        "research_only": True,
        "lookback_period": "1y",
        "symbols_requested": ["AAA", "BBB", "CCC"],
        "symbols_used": ["AAA", "BBB", "CCC"],
        "pairs_evaluated": 3,
        "pairs_returned": 3,
        "cointegrated_count": 1,
        "statsmodels_available": True,
        "notes": ["fixture run"],
    }
    pairs = [
        {
            "pair": ["AAA", "BBB"],
            "symbol_y": "AAA",
            "symbol_x": "BBB",
            "p_value": 0.01,
            "cointegrated_5pct": True,
            "latest_z_score": -1.2,
            "sufficient": True,
        }
    ]
    config = {"symbols_requested": ["AAA", "BBB", "CCC"], "lookback_period": "1y"}
    now = _utcnow()
    engine = get_engine()
    with Session(engine) as session:
        session.add(
            PairsResearchRun(
                run_id=run_id,
                status="completed",
                config_json=json.dumps(config),
                summary_json=json.dumps(summary),
                pairs_json=json.dumps(pairs),
                started_at=now - timedelta(minutes=5),
                finished_at=now,
            )
        )
        session.commit()
    return run_id


def seed_job_queue(*, status: str = "completed", job_name: str = "ic_panel") -> str:
    now = _utcnow()
    job_id = f"job_{job_name}_fixture"
    engine = get_engine()
    with Session(engine) as session:
        session.add(
            JobQueueItem(
                job_id=job_id,
                job_name=job_name,
                payload_json="{}",
                status=status,
                strategy_version="test_v1",
                factor_model_version="test_f1",
                created_at=now - timedelta(hours=2),
                started_at=now - timedelta(hours=1),
                finished_at=now,
                error_message="fixture failure" if status == "failed" else None,
            )
        )
        session.commit()
    return job_id


def seed_quant_lab_demo(*, sleeve: str = "medium") -> dict[str, Any]:
    """Populate an isolated DB with representative Quant Lab evidence."""
    seed_factor_ic(sleeve=sleeve)
    wf_id = seed_walk_forward_run(sleeve=sleeve)
    seed_predictions(resolved=4, unresolved=2)
    pairs_id = seed_pairs_run()
    seed_job_queue(status="completed")
    seed_job_queue(status="failed", job_name="forward_labels")
    return {
        "sleeve": sleeve,
        "walk_forward_run_id": wf_id,
        "pairs_run_id": pairs_id,
    }
