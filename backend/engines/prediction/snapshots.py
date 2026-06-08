"""Prediction snapshot persistence and outcome resolution."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd
from sqlalchemy.orm import Session

from config import FACTOR_MODEL_VERSION, PREDICTION_OUTCOME_HORIZONS
from data.db_engine import get_engine
from data.price_service import PriceService
from data.sector_map import sector_etf
from engines.quant_models import PredictionOutcome, PredictionSnapshot

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def persist_prediction_snapshot(
    *,
    symbol: str,
    sleeve: str,
    price: float,
    recommendation: str,
    confidence: float,
    time_horizon_days: int,
    alpha_score: float | None = None,
    valuation_score: float | None = None,
    catalyst_score: float | None = None,
    risk_score: float | None = None,
    data_confidence: float | None = None,
    market_regime: str | None = None,
    expected_return_pct: float | None = None,
    expected_downside_pct: float | None = None,
    features: dict[str, Any] | None = None,
    thesis: dict[str, Any] | None = None,
    source: str = "v2_score",
    trade_id: int | None = None,
) -> int | None:
    engine = get_engine()
    with Session(engine) as session:
        row = PredictionSnapshot(
            symbol=symbol.upper(),
            sleeve=sleeve,
            created_at=_utcnow(),
            price=float(price),
            recommendation=recommendation,
            confidence=float(confidence),
            time_horizon_days=int(time_horizon_days),
            alpha_score=alpha_score,
            valuation_score=valuation_score,
            catalyst_score=catalyst_score,
            risk_score=risk_score,
            data_confidence=data_confidence,
            market_regime=market_regime,
            expected_return_pct=expected_return_pct,
            expected_downside_pct=expected_downside_pct,
            model_version=FACTOR_MODEL_VERSION,
            source=source,
            trade_id=trade_id,
            features_json=json.dumps(features or {}),
            thesis_json=json.dumps(thesis or {}),
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return row.id


def find_today_snapshot(symbol: str, sleeve: str, *, source: str | None = None) -> int | None:
    """Reuse same-day snapshot for journal linking."""
    today = _utcnow().strftime("%Y-%m-%d")
    engine = get_engine()
    with Session(engine) as session:
        q = session.query(PredictionSnapshot).filter(
            PredictionSnapshot.symbol == symbol.upper(),
            PredictionSnapshot.sleeve == sleeve,
        )
        if source:
            q = q.filter(PredictionSnapshot.source == source)
        rows = q.order_by(PredictionSnapshot.created_at.desc()).limit(20).all()
        for r in rows:
            if r.created_at.strftime("%Y-%m-%d") == today:
                return r.id
    return None


def link_trade_to_snapshot(trade_id: int, snapshot_id: int) -> None:
    from engines.quant_models import TradePrediction

    engine = get_engine()
    with Session(engine) as session:
        row = session.get(TradePrediction, trade_id)
        if row:
            row.snapshot_id = snapshot_id
        snap = session.get(PredictionSnapshot, snapshot_id)
        if snap:
            snap.trade_id = trade_id
            snap.source = "trade_journal"
        session.commit()


def _forward_return(hist: pd.DataFrame, start_date, days: int) -> float | None:
    from utils.trading_calendar import forward_return_sessions, to_session_date

    d = to_session_date(start_date)
    if d is None:
        return None
    return forward_return_sessions(hist, d, days)


def _max_drawdown(hist: pd.DataFrame, start_idx: int, days: int) -> float | None:
    end = min(start_idx + days + 1, len(hist))
    window = hist["close"].iloc[start_idx:end]
    if len(window) < 2:
        return None
    peak = window.cummax()
    dd = (window / peak - 1).min()
    return round(float(dd) * 100, 4)


def _resolve_one(
    snap: PredictionSnapshot,
    ps: PriceService,
    spy_hist: pd.DataFrame,
    sector_hist_cache: dict[str, pd.DataFrame],
) -> dict[str, Any] | None:
    sym = snap.symbol
    hist = ps.get_history(sym, period="2y")
    if hist.empty:
        return None

    hist = hist.reset_index(drop=True)
    created = snap.created_at
    if created.tzinfo:
        created = created.replace(tzinfo=None)

    created = snap.created_at
    if created.tzinfo:
        created = created.replace(tzinfo=None)
    start_date = created.date()

    returns: dict[str, float | None] = {}
    for h in PREDICTION_OUTCOME_HORIZONS:
        returns[f"return_{h}d"] = _forward_return(hist, start_date, h)

    spy_r: dict[int, float | None] = {}
    if not spy_hist.empty:
        spy_hist = spy_hist.reset_index(drop=True)
        for h in (20, 60, 90):
            spy_r[h] = _forward_return(spy_hist, start_date, h)

    sector = None
    features = json.loads(snap.features_json or "{}")
    sector_name = features.get("sector")
    etf = sector_etf(sector_name) if sector_name else None
    sector_r: dict[int, float | None] = {}
    if etf:
        if etf not in sector_hist_cache:
            sector_hist_cache[etf] = ps.get_history(etf, period="2y")
        sec_hist = sector_hist_cache[etf]
        if not sec_hist.empty:
            sec_hist = sec_hist.reset_index(drop=True)
            for h in (20, 60, 90):
                sector_r[h] = _forward_return(sec_hist, start_date, h)

    r20 = returns.get("return_20d")
    r60 = returns.get("return_60d")
    r90 = returns.get("return_90d")
    from utils.trading_calendar import align_price_index_to_session

    idx = align_price_index_to_session(hist, start_date) or 0
    max_dd = _max_drawdown(hist, idx, 60)

    hit_target = None
    hit_stop = None
    if r60 is not None and snap.expected_return_pct is not None:
        hit_target = r60 >= snap.expected_return_pct
    if r60 is not None and snap.expected_downside_pct is not None:
        hit_stop = r60 <= -abs(snap.expected_downside_pct)

    return {
        "prediction_id": snap.id,
        "return_5d": returns.get("return_5d"),
        "return_20d": r20,
        "return_60d": r60,
        "return_90d": returns.get("return_90d"),
        "excess_vs_spy_20d": round(r20 - spy_r[20], 4) if r20 is not None and spy_r.get(20) is not None else None,
        "excess_vs_spy_60d": round(r60 - spy_r[60], 4) if r60 is not None and spy_r.get(60) is not None else None,
        "excess_vs_sector_20d": round(r20 - sector_r[20], 4) if r20 is not None and sector_r.get(20) is not None else None,
        "excess_vs_sector_60d": round(r60 - sector_r[60], 4) if r60 is not None and sector_r.get(60) is not None else None,
        "excess_vs_spy_90d": round(r90 - spy_r[90], 4) if r90 is not None and spy_r.get(90) is not None else None,
        "excess_vs_sector_90d": round(r90 - sector_r[90], 4) if r90 is not None and sector_r.get(90) is not None else None,
        "max_drawdown_60d": max_dd,
        "horizon_type": "trading_sessions",
        "hit_target": hit_target,
        "hit_stop": hit_stop,
    }


def resolve_prediction_outcomes(*, min_age_days: int = 5) -> dict[str, Any]:
    """Resolve outcomes for snapshots old enough to have forward returns."""
    engine = get_engine()
    ps = PriceService()
    spy_hist = ps.get_spy_history(period="2y")
    sector_cache: dict[str, pd.DataFrame] = {}
    cutoff = _utcnow() - timedelta(days=min_age_days)
    max_horizon = max(PREDICTION_OUTCOME_HORIZONS)
    oldest_needed = _utcnow() - timedelta(days=max_horizon + 5)

    resolved = 0
    skipped = 0
    with Session(engine) as session:
        snaps = (
            session.query(PredictionSnapshot)
            .filter(PredictionSnapshot.created_at <= cutoff)
            .filter(PredictionSnapshot.created_at >= oldest_needed)
            .order_by(PredictionSnapshot.created_at.asc())
            .limit(500)
            .all()
        )
        for snap in snaps:
            existing = session.get(PredictionOutcome, snap.id)
            if existing and existing.return_90d is not None:
                skipped += 1
                continue
            payload = _resolve_one(snap, ps, spy_hist, sector_cache)
            if not payload:
                skipped += 1
                continue
            row = PredictionOutcome(
                prediction_id=snap.id,
                return_5d=payload["return_5d"],
                return_20d=payload["return_20d"],
                return_60d=payload["return_60d"],
                return_90d=payload["return_90d"],
                excess_vs_spy_20d=payload["excess_vs_spy_20d"],
                excess_vs_spy_60d=payload["excess_vs_spy_60d"],
                excess_vs_sector_20d=payload["excess_vs_sector_20d"],
                excess_vs_sector_60d=payload["excess_vs_sector_60d"],
                excess_vs_spy_90d=payload.get("excess_vs_spy_90d"),
                excess_vs_sector_90d=payload.get("excess_vs_sector_90d"),
                max_drawdown_60d=payload["max_drawdown_60d"],
                hit_target=payload["hit_target"],
                hit_stop=payload["hit_stop"],
                resolved_at=_utcnow(),
            )
            if existing:
                session.merge(row)
            else:
                session.add(row)
            resolved += 1
        session.commit()

    return {"resolved": resolved, "skipped": skipped, "horizons": PREDICTION_OUTCOME_HORIZONS}


def list_recent_snapshots(
    limit: int = 50,
    symbol: str | None = None,
    *,
    source: str | None = None,
    sleeve: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
) -> list[dict[str, Any]]:
    engine = get_engine()
    with Session(engine) as session:
        q = session.query(PredictionSnapshot).order_by(PredictionSnapshot.created_at.desc())
        if symbol:
            q = q.filter(PredictionSnapshot.symbol == symbol.upper())
        if source:
            q = q.filter(PredictionSnapshot.source == source)
        if sleeve:
            q = q.filter(PredictionSnapshot.sleeve == sleeve)
        if from_date:
            q = q.filter(PredictionSnapshot.created_at >= from_date)
        if to_date:
            q = q.filter(PredictionSnapshot.created_at <= f"{to_date} 23:59:59")
        rows = q.limit(limit).all()
        out = []
        for r in rows:
            outcome = session.get(PredictionOutcome, r.id)
            out.append(
                {
                    "id": r.id,
                    "symbol": r.symbol,
                    "sleeve": r.sleeve,
                    "created_at": r.created_at.isoformat(),
                    "price": r.price,
                    "recommendation": r.recommendation,
                    "confidence": r.confidence,
                    "source": r.source,
                    "trade_id": r.trade_id,
                    "alpha_score": r.alpha_score,
                    "valuation_score": r.valuation_score,
                    "data_confidence": r.data_confidence,
                    "outcome": {
                        "return_20d": outcome.return_20d if outcome else None,
                        "return_60d": outcome.return_60d if outcome else None,
                        "excess_vs_spy_60d": outcome.excess_vs_spy_60d if outcome else None,
                    }
                    if outcome
                    else None,
                }
            )
        return out
