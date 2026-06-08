"""Persist v2 score attribution and risk rows."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from config import FACTOR_MODEL_VERSION, STRATEGY_VERSION
from data.db_engine import get_engine
from engines.quant_models import PositionRecommendation, RiskScoreRow, ScoreAttribution


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _today() -> str:
    return _utcnow().strftime("%Y-%m-%d")


def persist_score_attribution(
    *,
    symbol: str,
    sleeve: str,
    raw_score: float,
    dq_multiplier: float,
    risk_deduction: float,
    regime_mult: float,
    sector_tilt: float,
    final_score: float,
    factors: list[dict],
    weights: dict[str, float],
    as_of_date: str | None = None,
) -> None:
    engine = get_engine()
    as_of = as_of_date or _today()
    with Session(engine) as session:
        row = (
            session.query(ScoreAttribution)
            .filter(
                ScoreAttribution.symbol == symbol.upper(),
                ScoreAttribution.sleeve == sleeve,
                ScoreAttribution.as_of_date == as_of,
            )
            .first()
        )
        payload = dict(
            symbol=symbol.upper(),
            sleeve=sleeve,
            as_of_date=as_of,
            raw_score=raw_score,
            dq_multiplier=dq_multiplier,
            risk_deduction=risk_deduction,
            regime_mult=regime_mult,
            sector_tilt=sector_tilt,
            final_score=final_score,
            factors_json=json.dumps(factors),
            weights_json=json.dumps(weights),
            strategy_version=STRATEGY_VERSION,
        )
        if row:
            for key, val in payload.items():
                setattr(row, key, val)
        else:
            session.add(ScoreAttribution(**payload))
        session.commit()

    from engines.audit.logger import audit_log

    audit_log(
        "score_attribution_persisted",
        symbol=symbol,
        sleeve=sleeve,
        payload={"final_score": final_score, "as_of_date": as_of},
    )


def persist_risk_score(
    *,
    symbol: str,
    sleeve: str,
    risk_score: float,
    deduction_pts: float,
    breakdown: list[dict],
    as_of_date: str | None = None,
) -> None:
    engine = get_engine()
    as_of = as_of_date or _today()
    with Session(engine) as session:
        row = (
            session.query(RiskScoreRow)
            .filter(
                RiskScoreRow.symbol == symbol.upper(),
                RiskScoreRow.sleeve == sleeve,
                RiskScoreRow.as_of_date == as_of,
            )
            .first()
        )
        payload = dict(
            symbol=symbol.upper(),
            sleeve=sleeve,
            as_of_date=as_of,
            risk_score=risk_score,
            deduction_pts=deduction_pts,
            breakdown_json=json.dumps(breakdown),
        )
        if row:
            for key, val in payload.items():
                setattr(row, key, val)
        else:
            session.add(RiskScoreRow(**payload))
        session.commit()


def persist_position_recommendation(
    *,
    symbol: str,
    sleeve: str,
    recommended_pct: float,
    max_pct: float,
    stop_loss_pct: float | None,
    portfolio_alloc_pct: float,
    inputs: dict,
    as_of_date: str | None = None,
) -> None:
    engine = get_engine()
    as_of = as_of_date or _today()
    with Session(engine) as session:
        row = (
            session.query(PositionRecommendation)
            .filter(
                PositionRecommendation.symbol == symbol.upper(),
                PositionRecommendation.sleeve == sleeve,
                PositionRecommendation.as_of_date == as_of,
            )
            .first()
        )
        payload = dict(
            symbol=symbol.upper(),
            sleeve=sleeve,
            as_of_date=as_of,
            recommended_pct=recommended_pct,
            max_pct=max_pct,
            stop_loss_pct=stop_loss_pct,
            portfolio_alloc_pct=portfolio_alloc_pct,
            inputs_json=json.dumps(inputs),
        )
        if row:
            for key, val in payload.items():
                setattr(row, key, val)
        else:
            session.add(PositionRecommendation(**payload))
        session.commit()
