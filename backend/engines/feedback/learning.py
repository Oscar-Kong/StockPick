"""Monthly trade-feedback learning — aggregates closed-trade errors for ops review."""
from __future__ import annotations

import json
import logging
from collections import defaultdict

from config import TRADE_FEEDBACK_ENABLED
from data.db_engine import get_engine
from engines.quant_models import TradeOutcome

logger = logging.getLogger(__name__)


def run_trade_feedback_learning() -> dict:
    """Summarize prediction errors by factor attribution (IC panel job remains primary)."""
    if not TRADE_FEEDBACK_ENABLED:
        return {"skipped": True, "reason": "TRADE_FEEDBACK_ENABLED=false"}

    from sqlalchemy.orm import Session

    engine = get_engine()
    factor_errors: dict[str, list[float]] = defaultdict(list)
    errors: list[float] = []

    with Session(engine) as session:
        outcomes = session.query(TradeOutcome).all()
        for oc in outcomes:
            if oc.prediction_error_pct is not None:
                errors.append(float(oc.prediction_error_pct))
            raw = oc.factor_attribution_json or "{}"
            try:
                factors = json.loads(raw) if isinstance(raw, str) else raw
            except Exception:
                factors = {}
            for fid, beta in (factors or {}).items():
                factor_errors[fid].append(float(beta))

    per_factor = {
        fid: round(sum(vals) / len(vals), 4)
        for fid, vals in factor_errors.items()
        if vals
    }

    return {
        "outcomes_count": len(errors),
        "mean_prediction_error_pct": round(sum(errors) / len(errors), 4) if errors else None,
        "mean_factor_attribution": per_factor,
        "note": "Use quant IC panel + rebalance for weight updates; trade loop feeds retire/promote admin",
    }
