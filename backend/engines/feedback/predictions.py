"""Persist and compute trade predictions / outcomes."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from data.db_engine import get_engine
from data.strategy_registry import DEFAULT_STRATEGIES
from engines.quant_models import TradeOutcome, TradePrediction
from utils.datetime_util import utc_iso_z

logger = logging.getLogger(__name__)

_HORIZON_DAYS = {"penny": 14, "compounder": 365}
_TARGET_PCT = {"penny": 15.0, "compounder": 25.0}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def infer_sleeve(symbol: str, setup_tags: list[str] | None = None) -> str:
    from core.sleeve import normalize_sleeve

    tags = {t.lower() for t in (setup_tags or [])}
    for sleeve in ("penny", "compounder"):
        if sleeve in tags:
            return sleeve
    try:
        from data import cache as cache_module

        wl = cache_module.get_watchlist()
        sym = symbol.upper()
        for row in wl:
            if str(row.get("symbol", "")).upper() == sym:
                bucket = normalize_sleeve(str(row.get("bucket") or row.get("sleeve") or ""))
                if bucket in _HORIZON_DAYS:
                    return bucket
    except Exception:
        pass
    return "penny"


def expected_return_from_score(score: float, sleeve: str) -> float:
    """Map final score (0–100) to horizon-scaled expected return %."""
    target = _TARGET_PCT.get(sleeve, 10.0)
    edge = (float(score) - 50.0) / 50.0
    return round(edge * target, 4)


def horizon_days_for_sleeve(sleeve: str) -> int:
    key = f"{sleeve}_v1"
    cfg = DEFAULT_STRATEGIES.get(key, {})
    return int(cfg.get("hold_horizon_days") or _HORIZON_DAYS.get(sleeve, 20))


def factor_attribution(
    factors: list[dict[str, Any]],
    error_pct: float,
) -> dict[str, float]:
    """Simplified attribution: beta_i ∝ norm_score * error."""
    if not factors:
        return {}
    weighted: dict[str, float] = {}
    denom = 0.0
    for f in factors:
        fid = str(f.get("factor_id") or "")
        ns = abs(float(f.get("norm_score") or 0))
        if not fid:
            continue
        weighted[fid] = ns
        denom += ns
    if denom <= 0:
        return {}
    scale = float(error_pct) / denom
    return {k: round(v * scale, 4) for k, v in weighted.items()}


def save_prediction(
    *,
    trade_id: int,
    symbol: str,
    sleeve: str,
    expected_return_pct: float,
    horizon_days: int,
    score_snapshot: float,
    dq_multiplier: float | None,
    risk_deduction: float | None,
    factors: list[dict[str, Any]],
    weights: dict[str, float],
) -> None:
    engine = get_engine()
    with Session(engine) as session:
        row = session.get(TradePrediction, trade_id)
        if row is None:
            row = TradePrediction(trade_id=trade_id, created_at=_utcnow())
            session.add(row)
        row.symbol = symbol.upper()
        row.sleeve = sleeve
        row.expected_return_pct = expected_return_pct
        row.horizon_days = horizon_days
        row.score_snapshot = score_snapshot
        row.dq_multiplier = dq_multiplier
        row.risk_deduction = risk_deduction
        row.factors_json = json.dumps(factors)
        row.weights_json = json.dumps(weights)
        session.commit()


def save_outcome(
    *,
    trade_id: int,
    actual_return_pct: float,
    prediction_error_pct: float | None,
    factor_attribution_json: dict[str, float],
) -> None:
    engine = get_engine()
    with Session(engine) as session:
        existing = session.get(TradeOutcome, trade_id)
        row = TradeOutcome(
            trade_id=trade_id,
            actual_return_pct=actual_return_pct,
            prediction_error_pct=prediction_error_pct,
            factor_attribution_json=json.dumps(factor_attribution_json),
            closed_at=_utcnow(),
        )
        if existing:
            session.merge(row)
        else:
            session.add(row)
        session.commit()


def get_prediction(trade_id: int) -> dict[str, Any] | None:
    engine = get_engine()
    with Session(engine) as session:
        row = session.get(TradePrediction, trade_id)
        if not row:
            return None
        return {
            "trade_id": row.trade_id,
            "symbol": row.symbol,
            "sleeve": row.sleeve,
            "snapshot_id": getattr(row, "snapshot_id", None),
            "expected_return_pct": row.expected_return_pct,
            "horizon_days": row.horizon_days,
            "score_snapshot": row.score_snapshot,
            "dq_multiplier": row.dq_multiplier,
            "risk_deduction": row.risk_deduction,
            "factors": json.loads(row.factors_json or "[]"),
            "weights": json.loads(row.weights_json or "{}"),
            "created_at": utc_iso_z(row.created_at),
        }


def get_outcome(trade_id: int) -> dict[str, Any] | None:
    engine = get_engine()
    with Session(engine) as session:
        row = session.get(TradeOutcome, trade_id)
        if not row:
            return None
        return {
            "trade_id": row.trade_id,
            "actual_return_pct": row.actual_return_pct,
            "prediction_error_pct": row.prediction_error_pct,
            "factor_attribution": json.loads(row.factor_attribution_json or "{}"),
            "closed_at": utc_iso_z(row.closed_at),
        }


def list_recent_outcomes(limit: int = 50) -> list[dict[str, Any]]:
    engine = get_engine()
    with Session(engine) as session:
        rows = (
            session.query(TradeOutcome)
            .order_by(TradeOutcome.closed_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "trade_id": r.trade_id,
                "actual_return_pct": r.actual_return_pct,
                "prediction_error_pct": r.prediction_error_pct,
                "closed_at": utc_iso_z(r.closed_at),
            }
            for r in rows
        ]
