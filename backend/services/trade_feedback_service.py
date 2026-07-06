"""Hook trade journal to unified prediction snapshot / outcome store."""
from __future__ import annotations

import logging
from typing import Any

from config import PREDICTION_SNAPSHOTS_ENABLED, SCORE_ENGINE_V2_ENABLED, TRADE_FEEDBACK_ENABLED
from engines.feedback.predictions import (
    expected_return_from_score,
    factor_attribution,
    get_outcome,
    get_prediction,
    horizon_days_for_sleeve,
    infer_sleeve,
    list_recent_outcomes,
    save_outcome,
    save_prediction,
)
from engines.feedback.factor_lifecycle import build_factor_admin

logger = logging.getLogger(__name__)


def _snapshot_from_v2(symbol: str, sleeve: str, *, persist: bool = True) -> dict[str, Any] | None:
    if not SCORE_ENGINE_V2_ENABLED:
        return None
    try:
        from services.quant_v2_service import build_v2_score

        result = build_v2_score(
            symbol,
            sleeve,
            validate_parity=False,
            persist_snapshot=persist and PREDICTION_SNAPSHOTS_ENABLED,
        )
        if isinstance(result, dict) and result.get("error"):
            return None
        factors = [
            {
                "factor_id": f.factor_id,
                "norm_score": f.norm_score,
                "weight": f.weight,
                "contribution": f.contribution,
            }
            for f in result.factors
        ]
        weights = {f.factor_id: f.weight for f in result.factors}
        attr = result.attribution
        return {
            "score": float(result.score),
            "dq_multiplier": attr.dq_multiplier,
            "risk_deduction": attr.risk_deduction,
            "factors": factors,
            "weights": weights,
            "snapshot_id": result.prediction_snapshot_id,
        }
    except Exception as exc:
        logger.debug("v2 snapshot failed for %s: %s", symbol, exc)
        return None


def record_prediction_for_trade(
    trade_id: int,
    *,
    symbol: str,
    side: str,
    entry_price: float,
    setup_tags: list[str] | None = None,
    sleeve: str | None = None,
) -> dict[str, Any] | None:
    if not TRADE_FEEDBACK_ENABLED:
        return None
    from core.sleeve import normalize_sleeve

    sleeve_val = normalize_sleeve(sleeve or infer_sleeve(symbol, setup_tags))

    from engines.prediction.snapshots import find_today_snapshot, link_trade_to_snapshot

    snapshot_id = find_today_snapshot(symbol, sleeve_val)
    snap = None
    if snapshot_id is None:
        snap = _snapshot_from_v2(symbol, sleeve_val, persist=True)
        snapshot_id = snap.get("snapshot_id") if snap else None
    else:
        snap = _snapshot_from_v2(symbol, sleeve_val, persist=False) or {}

    if snapshot_id:
        link_trade_to_snapshot(trade_id, snapshot_id)

    score = float(snap.get("score", 50.0)) if snap else 50.0
    expected = expected_return_from_score(score, sleeve_val)
    horizon = horizon_days_for_sleeve(sleeve_val)
    factors = snap.get("factors", []) if snap else []
    weights = snap.get("weights", {}) if snap else {}

    from engines.audit.logger import audit_log

    save_prediction(
        trade_id=trade_id,
        symbol=symbol,
        sleeve=sleeve_val,
        expected_return_pct=expected,
        horizon_days=horizon,
        score_snapshot=score,
        dq_multiplier=snap.get("dq_multiplier") if snap else None,
        risk_deduction=snap.get("risk_deduction") if snap else None,
        factors=factors,
        weights=weights,
    )
    if snapshot_id:
        from engines.quant_models import TradePrediction
        from data.db_engine import get_engine
        from sqlalchemy.orm import Session

        with Session(get_engine()) as session:
            row = session.get(TradePrediction, trade_id)
            if row:
                row.snapshot_id = snapshot_id
                session.commit()

    audit_log(
        "trade_prediction",
        symbol=symbol,
        sleeve=sleeve_val,
        payload={"trade_id": trade_id, "expected_return_pct": expected, "score": score, "snapshot_id": snapshot_id},
    )
    return {
        "trade_id": trade_id,
        "sleeve": sleeve_val,
        "expected_return_pct": expected,
        "horizon_days": horizon,
        "score_snapshot": score,
        "snapshot_id": snapshot_id,
    }


def record_outcome_for_trade(
    trade_id: int,
    *,
    side: str,
    entry_price: float,
    exit_price: float,
) -> dict[str, Any] | None:
    if not TRADE_FEEDBACK_ENABLED:
        return None
    ep = float(entry_price)
    xp = float(exit_price)
    if ep <= 0:
        return None
    if side.lower() == "short":
        actual = (ep - xp) / ep * 100.0
    else:
        actual = (xp - ep) / ep * 100.0

    pred = get_prediction(trade_id)
    error = None
    factors: list[dict[str, Any]] = []
    snapshot_id = pred.get("snapshot_id") if pred else None
    if pred:
        exp = pred.get("expected_return_pct")
        if exp is not None:
            error = round(actual - float(exp), 4)
        factors = pred.get("factors") or []

    attrib = factor_attribution(factors, error or 0.0)
    from engines.audit.logger import audit_log

    save_outcome(
        trade_id=trade_id,
        actual_return_pct=round(actual, 4),
        prediction_error_pct=error,
        factor_attribution_json=attrib,
    )

    if snapshot_id is None and pred:
        from engines.quant_models import TradePrediction
        from data.db_engine import get_engine
        from sqlalchemy.orm import Session

        with Session(get_engine()) as session:
            row = session.get(TradePrediction, trade_id)
            snapshot_id = row.snapshot_id if row else None

    if snapshot_id:
        try:
            from engines.prediction.snapshots import resolve_prediction_outcomes

            resolve_prediction_outcomes(min_age_days=0)
        except Exception as exc:
            logger.debug("snapshot outcome refresh: %s", exc)

    audit_log(
        "trade_outcome",
        payload={
            "trade_id": trade_id,
            "actual_return_pct": round(actual, 4),
            "prediction_error_pct": error,
            "snapshot_id": snapshot_id,
        },
    )
    return {
        "trade_id": trade_id,
        "actual_return_pct": round(actual, 4),
        "prediction_error_pct": error,
        "factor_attribution": attrib,
        "snapshot_id": snapshot_id,
    }


def feedback_summary() -> dict[str, Any]:
    outcomes = list_recent_outcomes(limit=200)
    errors = [o["prediction_error_pct"] for o in outcomes if o.get("prediction_error_pct") is not None]
    actuals = [o["actual_return_pct"] for o in outcomes if o.get("actual_return_pct") is not None]
    from engines.prediction.snapshots import list_recent_snapshots

    snaps = list_recent_snapshots(limit=200)
    return {
        "outcomes_count": len(outcomes),
        "snapshots_count": len(snaps),
        "mean_actual_return_pct": round(sum(actuals) / len(actuals), 4) if actuals else None,
        "mean_prediction_error_pct": round(sum(errors) / len(errors), 4) if errors else None,
        "recent_outcomes": outcomes[:20],
        "recent_snapshots": snaps[:10],
    }


def get_trade_feedback(trade_id: int) -> dict[str, Any]:
    pred = get_prediction(trade_id)
    outcome = get_outcome(trade_id)
    snap_outcome = None
    if pred and pred.get("snapshot_id"):
        from engines.quant_models import PredictionOutcome
        from data.db_engine import get_engine
        from sqlalchemy.orm import Session

        with Session(get_engine()) as session:
            oc = session.get(PredictionOutcome, pred["snapshot_id"])
            if oc:
                snap_outcome = {
                    "return_60d": oc.return_60d,
                    "excess_vs_spy_60d": oc.excess_vs_spy_60d,
                }
    return {"prediction": pred, "outcome": outcome, "snapshot_outcome": snap_outcome}


def factor_admin_view(sleeve: str | None = None) -> dict[str, Any]:
    admin = build_factor_admin(sleeve)
    try:
        from engines.feedback.outcome_weights import run_outcome_weight_feedback

        admin["outcome_feedback_preview"] = run_outcome_weight_feedback(sleeve=sleeve)
    except Exception:
        pass
    return admin
