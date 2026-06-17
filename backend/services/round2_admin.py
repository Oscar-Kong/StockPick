"""Round 2 operational metrics for admin dashboards."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from config import FACTOR_MODEL_VERSION, PREDICTION_SNAPSHOTS_ENABLED
from data.db_engine import get_engine
from engines.quant_models import (
    FactorIcHistory,
    ForwardReturnLabel,
    FundamentalsPit,
    PredictionOutcome,
    PredictionSnapshot,
)


def round2_ops_stats() -> dict:
    engine = get_engine()
    today_dt = datetime.now(timezone.utc).replace(tzinfo=None)
    week_dt = today_dt - timedelta(days=7)
    today = today_dt.strftime("%Y-%m-%d")

    try:
        with Session(engine) as session:
            snap_total = session.query(func.count(PredictionSnapshot.id)).scalar() or 0
            snap_week = (
                session.query(func.count(PredictionSnapshot.id))
                .filter(PredictionSnapshot.created_at >= week_dt)
                .scalar()
                or 0
            )
            outcomes_resolved = (
                session.query(func.count(PredictionOutcome.prediction_id))
                .filter(PredictionOutcome.resolved_at.isnot(None))
                .scalar()
                or 0
            )
            labels = session.query(func.count(ForwardReturnLabel.id)).scalar() or 0
            pit_rows = session.query(func.count(FundamentalsPit.id)).scalar() or 0
            ic_latest = (
                session.query(FactorIcHistory.as_of_date)
                .order_by(FactorIcHistory.as_of_date.desc())
                .limit(1)
                .scalar()
            )
            strong_buy_gated = (
                session.query(func.count(PredictionSnapshot.id))
                .filter(PredictionSnapshot.recommendation == "strong_buy")
                .scalar()
                or 0
            )
    except Exception:
        snap_total = snap_week = outcomes_resolved = labels = pit_rows = strong_buy_gated = 0
        ic_latest = None

    return {
        "model_version": FACTOR_MODEL_VERSION,
        "prediction_snapshots_enabled": bool(PREDICTION_SNAPSHOTS_ENABLED),
        "snapshots_total": snap_total,
        "snapshots_last_7d": snap_week,
        "outcomes_resolved": outcomes_resolved,
        "forward_label_rows": labels,
        "pit_fundamental_rows": pit_rows,
        "ic_panel_latest_date": ic_latest,
        "strong_buy_snapshots": strong_buy_gated,
        "as_of": today,
    }
