"""Factor retire/promote recommendations from IC history + trade outcomes."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from data.db_engine import get_engine
from engines.quant_models import FactorDefinition, FactorIcHistory, TradeOutcome, TradePrediction

RETIRE_IR_THRESHOLD = 0.3
RETIRE_MONTHS = 6
PROMOTE_IR_THRESHOLD = 1.0
PROMOTE_MONTHS = 3


def _cutoff_date(months: int) -> str:
    dt = datetime.now(timezone.utc) - timedelta(days=months * 30)
    return dt.strftime("%Y-%m-%d")


def _avg_ir(session: Session, factor_id: str, sleeve: str, since: str) -> float | None:
    rows = (
        session.query(func.avg(FactorIcHistory.ir))
        .filter(
            FactorIcHistory.factor_id == factor_id,
            FactorIcHistory.sleeve == sleeve,
            FactorIcHistory.as_of_date >= since,
            FactorIcHistory.ir.isnot(None),
        )
        .scalar()
    )
    if rows is None:
        return None
    return float(rows)


def build_factor_admin(sleeve: str | None = None) -> dict[str, Any]:
    engine = get_engine()
    retire_since = _cutoff_date(RETIRE_MONTHS)
    promote_since = _cutoff_date(PROMOTE_MONTHS)
    out: list[dict[str, Any]] = []

    with Session(engine) as session:
        q = session.query(FactorDefinition)
        if sleeve:
            q = q.filter(FactorDefinition.sleeve == sleeve)
        factors = q.all()

        closed = session.query(TradeOutcome).count()
        preds = session.query(TradePrediction).count()

        for fd in factors:
            avg_ir = _avg_ir(session, fd.factor_id, fd.sleeve, retire_since)
            recent_ir = _avg_ir(session, fd.factor_id, fd.sleeve, promote_since)
            action = "hold"
            reason = ""
            if avg_ir is not None and avg_ir < RETIRE_IR_THRESHOLD:
                action = "retire"
                reason = f"avg IR {avg_ir:.2f} < {RETIRE_IR_THRESHOLD} over {RETIRE_MONTHS}mo"
            elif recent_ir is not None and recent_ir >= PROMOTE_IR_THRESHOLD:
                action = "promote"
                reason = f"recent IR {recent_ir:.2f} >= {PROMOTE_IR_THRESHOLD} over {PROMOTE_MONTHS}mo"
            elif avg_ir is None:
                reason = "insufficient IC history"

            out.append(
                {
                    "factor_id": fd.factor_id,
                    "sleeve": fd.sleeve,
                    "display_name": fd.display_name,
                    "is_active": fd.is_active,
                    "formula_version": fd.formula_version,
                    "avg_ir_6mo": round(avg_ir, 4) if avg_ir is not None else None,
                    "avg_ir_3mo": round(recent_ir, 4) if recent_ir is not None else None,
                    "recommended_action": action,
                    "reason": reason,
                }
            )

    return {
        "factors": out,
        "trade_predictions_count": preds,
        "trade_outcomes_count": closed,
        "sleeve_filter": sleeve,
    }
