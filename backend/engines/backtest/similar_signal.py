"""Similar-signal historical backtest — match current factor profile to past cases."""
from __future__ import annotations

import json
import logging
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from config import SIMILAR_SIGNAL_TOLERANCE
from data.db_engine import get_engine
from data.historical_store import FactorSnapshot
from data.price_service import PriceService
from engines.quant_models import MarketRegime
from engines.weighting.regime_classifier import classify_spy

logger = logging.getLogger(__name__)


def _factor_vector(factors: list[dict[str, Any]]) -> dict[str, float]:
    out: dict[str, float] = {}
    for f in factors:
        fid = str(f.get("factor_id") or "")
        ns = f.get("norm_score")
        if fid and ns is not None:
            out[fid] = float(ns)
    return out


def _distance(a: dict[str, float], b: dict[str, float]) -> float:
    keys = set(a) & set(b)
    if not keys:
        return 999.0
    diffs = [abs(a[k] - b[k]) for k in keys]
    return float(np.mean(diffs))


def run_similar_signal_backtest(
    *,
    symbol: str,
    sleeve: str,
    current_factors: list[dict[str, Any]],
    market_regime: str | None = None,
    forward_days: int = 60,
) -> dict[str, Any]:
    """Find historical snapshots with similar factor profiles and measure forward returns."""
    current = _factor_vector(current_factors)
    if len(current) < 2:
        return {"error": "insufficient factors", "sample_n": 0}

    regime = market_regime
    if not regime:
        try:
            r = classify_spy()
            regime = r.regime if r else None
        except Exception:
            regime = None

    engine = get_engine()
    ps = PriceService()
    matches: list[dict[str, Any]] = []
    regime_at_date: dict[str, str | None] = {}

    def _regime_on(date_str: str) -> str | None:
        if date_str in regime_at_date:
            return regime_at_date[date_str]
        try:
            with Session(engine) as session:
                row = (
                    session.query(MarketRegime)
                    .filter(MarketRegime.as_of_date <= date_str)
                    .order_by(MarketRegime.as_of_date.desc())
                    .first()
                )
                regime_at_date[date_str] = row.regime if row else None
        except Exception:
            regime_at_date[date_str] = None
        return regime_at_date[date_str]

    with Session(engine) as session:
        rows = (
            session.query(FactorSnapshot)
            .filter(FactorSnapshot.bucket == sleeve)
            .order_by(FactorSnapshot.snapshot_date.desc())
            .limit(2000)
            .all()
        )

    for row in rows:
        if row.symbol == symbol.upper():
            continue
        try:
            past_factors = json.loads(row.factors_json or "{}")
        except Exception:
            continue
        if isinstance(past_factors, dict):
            past_vec = {k: float(v) for k, v in past_factors.items() if v is not None}
        else:
            past_vec = _factor_vector(past_factors if isinstance(past_factors, list) else [])
        dist = _distance(current, past_vec)
        if dist > SIMILAR_SIGNAL_TOLERANCE:
            continue
        if regime:
            snap_regime = _regime_on(row.snapshot_date)
            if snap_regime and snap_regime != regime:
                continue
        matches.append({"symbol": row.symbol, "date": row.snapshot_date, "distance": dist})

    if not matches:
        return {
            "sample_n": 0,
            "avg_forward_return_pct": None,
            "win_rate": None,
            "max_drawdown_pct": None,
            "best_regime": regime,
            "worst_regime": None,
            "matches": [],
        }

    returns: list[float] = []
    drawdowns: list[float] = []
    for m in matches[:40]:
        sym = m["symbol"]
        try:
            hist = ps.get_history(sym, period="2y")
            if hist.empty or len(hist) < forward_days + 10:
                continue
            hist = hist.reset_index(drop=True)
            date_str = m["date"]
            idx = None
            for i, ts in enumerate(hist.get("date", hist.index)):
                try:
                    if str(pd.Timestamp(ts).date()) >= date_str:
                        idx = i
                        break
                except Exception:
                    continue
            if idx is None or idx + forward_days >= len(hist):
                continue
            r = float(hist["close"].iloc[idx + forward_days] / hist["close"].iloc[idx] - 1) * 100
            returns.append(r)
            m["forward_return_pct"] = round(r, 2)
            window = hist["close"].iloc[idx : idx + forward_days + 1]
            peak = window.cummax()
            dd = float((window / peak - 1).min() * 100)
            m["max_drawdown_pct"] = round(dd, 2)
            drawdowns.append(dd)
        except Exception as exc:
            logger.debug("similar signal skip %s: %s", sym, exc)

    if not returns:
        return {"sample_n": 0, "matches": matches[:5], "error": "no forward returns computed"}

    arr = np.array(returns)
    return {
        "sample_n": len(returns),
        "avg_forward_return_pct": round(float(arr.mean()), 2),
        "median_forward_return_pct": round(float(np.median(arr)), 2),
        "win_rate": round(float(np.mean(arr > 0)), 3),
        "max_drawdown_pct": round(float(min(drawdowns)), 2) if drawdowns else None,
        "best_regime": regime,
        "worst_regime": "high_volatility_drawdown" if float(arr.mean()) < 0 else None,
        "forward_days": forward_days,
        "matches": matches[:8],
        "top_analogs": [m for m in matches if m.get("forward_return_pct") is not None][:5],
    }
