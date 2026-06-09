"""Cross-sectional IC / IR panel — persisted to factor_ic_history."""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from config import FACTOR_IC_LOOKBACK_DAYS, IC_PANEL_FORWARD_DAYS, IC_PANEL_MAX_SYMBOLS
from data.db_engine import get_engine
from data.price_service import PriceService
from engines.factor.catalog import active_factor_catalog
from engines.quant_models import FactorIcHistory
from engines.weighting.factor_series import catalog_factor_ids, factor_score_at_window

logger = logging.getLogger(__name__)


def _utc_today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _panel_symbols() -> list[str]:
    symbols: list[str] = []
    try:
        from data.cache import Cache

        cached = Cache().get("universe:sp500")
        if cached and cached.get("symbols"):
            symbols = list(cached["symbols"])
    except Exception:
        pass
    if not symbols:
        symbols = ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "JPM", "V", "UNH", "XOM"]
    return [s.upper() for s in symbols[:IC_PANEL_MAX_SYMBOLS]]


def _symbol_sector(symbol: str, ps: PriceService) -> str:
    try:
        info = ps.get_info(symbol) or {}
        return str(info.get("sector") or "Unknown")
    except Exception:
        return "Unknown"


def _pooled_ic(
    factor_id: str,
    symbols: list[str],
    *,
    forward_days: int,
    ps: PriceService | None = None,
) -> dict:
    ps = ps or PriceService()
    spy = ps.get_spy_history(period="2y")
    if spy.empty:
        return {"error": "no spy history"}

    scores: list[float] = []
    fwd_rets: list[float] = []
    sector_pairs: dict[str, list[tuple[float, float]]] = defaultdict(list)

    for sym in symbols:
        sector = _symbol_sector(sym, ps)
        try:
            hist = ps.get_history(sym, period="2y")
            if hist.empty or len(hist) < 80:
                continue
            hist = hist.reset_index(drop=True)
            spy_r = spy.reset_index(drop=True)
            start = max(60, len(hist) - FACTOR_IC_LOOKBACK_DAYS)
            for i in range(start, len(hist) - forward_days):
                window = hist.iloc[: i + 1]
                spy_w = spy_r.iloc[: min(i + 1, len(spy_r))]
                sc = factor_score_at_window(factor_id, window, spy_w, symbol=sym)
                if sc is None:
                    continue
                fwd = float(hist["close"].iloc[i + forward_days] / hist["close"].iloc[i] - 1.0)
                scores.append(sc)
                fwd_rets.append(fwd)
                sector_pairs[sector].append((sc, fwd))
        except Exception as exc:
            logger.debug("IC skip %s %s: %s", sym, factor_id, exc)

    if len(scores) < 40:
        return {"error": "insufficient pooled rows", "sample_n": len(scores)}

    arr_s = np.array(scores)
    arr_f = np.array(fwd_rets)
    ic = float(np.corrcoef(arr_s, arr_f)[0, 1])
    if np.isnan(ic):
        ic = 0.0

    hit = float(np.mean((arr_s > np.median(arr_s)) == (arr_f > 0)))
    spread = 0.0
    deciles: list[dict] = []
    try:
        df = pd.DataFrame({"score": arr_s, "fwd": arr_f})
        df["q"] = pd.qcut(df["score"], 5, labels=False, duplicates="drop")
        qm = df.groupby("q")["fwd"].mean()
        if len(qm) >= 2:
            spread = float(qm.iloc[-1] - qm.iloc[0])
        df["d"] = pd.qcut(df["score"], 10, labels=False, duplicates="drop")
        for q, g in df.groupby("d"):
            deciles.append(
                {
                    "decile": int(q) + 1,
                    "avg_forward_return_pct": round(float(g["fwd"].mean()) * 100, 3),
                    "sample_n": len(g),
                }
            )
    except Exception:
        pass

    ir = ic / max(0.05, abs(spread) + 0.01) if spread else ic / 0.1

    by_sector: dict[str, dict] = {}
    for sec, pairs in sector_pairs.items():
        if len(pairs) < 25:
            continue
        arr_sc = np.array([p[0] for p in pairs])
        arr_fw = np.array([p[1] for p in pairs])
        sec_ic = float(np.corrcoef(arr_sc, arr_fw)[0, 1])
        if np.isnan(sec_ic):
            sec_ic = 0.0
        by_sector[sec] = {
            "ic": round(sec_ic, 4),
            "sample_n": len(pairs),
            "hit_rate": round(float(np.mean((arr_sc > np.median(arr_sc)) == (arr_fw > 0))), 4),
        }

    return {
        "ic": round(ic, 4),
        "ir": round(float(ir), 4),
        "hit_rate": round(hit, 4),
        "sample_n": len(scores),
        "quintile_spread": round(spread * 100, 3),
        "deciles": deciles,
        "by_sector": by_sector,
    }


def persist_ic_row(
    session: Session,
    *,
    factor_id: str,
    sleeve: str,
    as_of_date: str,
    horizon_days: int,
    stats: dict,
) -> None:
    with session.no_autoflush:
        row = (
            session.query(FactorIcHistory)
            .filter(
                FactorIcHistory.factor_id == factor_id,
                FactorIcHistory.sleeve == sleeve,
                FactorIcHistory.as_of_date == as_of_date,
                FactorIcHistory.horizon_days == horizon_days,
            )
            .first()
        )
    payload = dict(
        factor_id=factor_id,
        sleeve=sleeve,
        as_of_date=as_of_date,
        horizon_days=horizon_days,
        ic=stats.get("ic"),
        ir=stats.get("ir"),
        hit_rate=stats.get("hit_rate"),
        sample_n=stats.get("sample_n"),
    )
    if row:
        for k, v in payload.items():
            setattr(row, k, v)
    else:
        session.add(FactorIcHistory(**payload))


def persist_decile_rows(
    session: Session,
    *,
    factor_id: str,
    sleeve: str,
    as_of_date: str,
    horizon_days: int,
    deciles: list[dict],
    regime: str | None = None,
) -> None:
    from engines.quant_models import FactorDecileHistory

    for d in deciles:
        dec = int(d.get("decile") or 0)
        if dec <= 0:
            continue
        with session.no_autoflush:
            row = (
                session.query(FactorDecileHistory)
                .filter(
                    FactorDecileHistory.factor_id == factor_id,
                    FactorDecileHistory.sleeve == sleeve,
                    FactorDecileHistory.as_of_date == as_of_date,
                    FactorDecileHistory.horizon_days == horizon_days,
                    FactorDecileHistory.decile == dec,
                )
                .first()
            )
        payload = dict(
            factor_id=factor_id,
            sleeve=sleeve,
            as_of_date=as_of_date,
            horizon_days=horizon_days,
            decile=dec,
            avg_forward_return=float(d.get("avg_forward_return_pct", 0)) / 100.0
            if d.get("avg_forward_return_pct") is not None
            else None,
            sample_n=d.get("sample_n"),
            regime=regime,
            sector=None,
        )
        if row:
            for k, v in payload.items():
                setattr(row, k, v)
        else:
            session.add(FactorDecileHistory(**payload))


def run_ic_panel(
    *,
    symbols: list[str] | None = None,
    sleeves: list[str] | None = None,
    forward_days: int | None = None,
    horizons: list[int] | None = None,
) -> dict:
    """Compute and persist IC panel for all catalog factors."""
    import os

    os.environ["IC_PANEL_OFFLINE"] = "1"
    from config import IC_PANEL_HORIZONS

    symbols = symbols or _panel_symbols()
    sleeves = sleeves or list(active_factor_catalog().keys())
    horizon_list = horizons or ([forward_days] if forward_days else IC_PANEL_HORIZONS)
    as_of = _utc_today()
    ps = PriceService()
    results: list[dict] = []
    engine = get_engine()
    regime_name = None
    try:
        from engines.weighting.weight_store import WeightStore

        regime_name = WeightStore.current_regime()
    except Exception:
        pass

    with Session(engine) as session:
        for horizon in horizon_list:
            for sleeve in sleeves:
                for factor_id in catalog_factor_ids(sleeve):
                    stats = _pooled_ic(factor_id, symbols, forward_days=horizon, ps=ps)
                    entry = {"factor_id": factor_id, "sleeve": sleeve, "horizon_days": horizon, **stats}
                    results.append(entry)
                    if "ic" in stats:
                        persist_ic_row(
                            session,
                            factor_id=factor_id,
                            sleeve=sleeve,
                            as_of_date=as_of,
                            horizon_days=horizon,
                            stats=stats,
                        )
                        if stats.get("deciles"):
                            persist_decile_rows(
                                session,
                                factor_id=factor_id,
                                sleeve=sleeve,
                                as_of_date=as_of,
                                horizon_days=horizon,
                                deciles=stats["deciles"],
                                regime=regime_name,
                            )
        session.commit()

    sector_cache: dict[str, dict] = {}
    for r in results:
        if not r.get("by_sector"):
            continue
        key = f"{r['factor_id']}:{r['sleeve']}:{r['horizon_days']}"
        sector_cache[key] = r["by_sector"]
    if sector_cache:
        try:
            from data.cache import Cache

            Cache().set(f"ic_by_sector:{as_of}", sector_cache, ttl=86400 * 7)
        except Exception:
            pass

    ok = [r for r in results if "ic" in r]
    return {
        "as_of_date": as_of,
        "horizons": horizon_list,
        "symbols_used": len(symbols),
        "factors_computed": len(ok),
        "factors_failed": len(results) - len(ok),
        "results": results,
    }


def load_latest_ic(sleeve: str, *, horizon_days: int | None = None) -> dict[str, dict]:
    """factor_id → {ic, ir, hit_rate, sample_n} for most recent as_of_date."""
    horizon = horizon_days or IC_PANEL_FORWARD_DAYS
    engine = get_engine()
    with Session(engine) as session:
        latest = (
            session.query(FactorIcHistory.as_of_date)
            .filter(FactorIcHistory.sleeve == sleeve, FactorIcHistory.horizon_days == horizon)
            .order_by(FactorIcHistory.as_of_date.desc())
            .limit(1)
            .scalar()
        )
        if not latest:
            return {}
        rows = (
            session.query(FactorIcHistory)
            .filter(
                FactorIcHistory.sleeve == sleeve,
                FactorIcHistory.as_of_date == latest,
                FactorIcHistory.horizon_days == horizon,
            )
            .all()
        )
        return {
            r.factor_id: {
                "ic": r.ic or 0.0,
                "ir": r.ir or 0.0,
                "hit_rate": r.hit_rate or 0.0,
                "sample_n": r.sample_n or 0,
            }
            for r in rows
        }
