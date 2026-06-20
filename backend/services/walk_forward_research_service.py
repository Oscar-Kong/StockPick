"""Unified walk-forward research pipeline — PIT universe, ScoringEngine, forward labels."""
from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Literal

import numpy as np
import pandas as pd

from config import FACTOR_MODEL_VERSION, STRATEGY_VERSION
from data.db_engine import get_engine
from data.universe import get_universe
from engines.backtest.universe_pit import active_symbols_on_date
from engines.quant_models import BacktestRun
from engines.risk.engine import RiskEngine
from engines.scoring.engine import ScoringEngine
from engines.store import persist_risk_score, persist_score_attribution
from quant_core.returns import simple_returns
from screeners.base import CandidateContext

logger = logging.getLogger(__name__)

RebalanceFrequency = Literal["weekly", "monthly", "quarterly"] | str

MIN_HISTORY_BARS = 60
DEFAULT_MAX_SYMBOLS = 30


@dataclass
class WalkForwardConfig:
    sleeve: str
    start_date: str
    end_date: str
    rebalance_frequency: str = "monthly"
    forward_horizons: list[int] = field(default_factory=lambda: [20])
    max_symbols: int = DEFAULT_MAX_SYMBOLS
    persist_snapshots: bool = True


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _safe_mean(values: list[float | None]) -> float | None:
    clean = [float(v) for v in values if v is not None]
    if not clean:
        return None
    return round(float(np.mean(clean)), 6)


def _parse_date(value: str) -> date:
    return date.fromisoformat(value[:10])


def _truncate_history(hist: pd.DataFrame, as_of: date) -> pd.DataFrame:
    """Keep rows with session date <= as_of (no look-ahead)."""
    if hist is None or hist.empty:
        return pd.DataFrame()
    df = hist.copy()
    if "date" not in df.columns:
        return pd.DataFrame()
    dates = pd.to_datetime(df["date"]).dt.date
    mask = dates <= as_of
    return df.loc[mask].reset_index(drop=True)


def rebalance_dates(
    start_date: str,
    end_date: str,
    frequency: str,
) -> list[date]:
    """Trading session rebalance dates between start and end (inclusive)."""
    start = _parse_date(start_date)
    end = _parse_date(end_date)
    if start > end:
        raise ValueError("start_date must be <= end_date")

    sessions: list[date] = []
    try:
        import exchange_calendars as xcals
        from config import SCHEDULER_MARKET_CALENDAR

        cal = xcals.get_calendar(SCHEDULER_MARKET_CALENDAR)
        idx = cal.sessions_in_range(pd.Timestamp(start), pd.Timestamp(end))
        sessions = [ts.date() for ts in idx]
    except Exception:
        bdays = pd.bdate_range(start, end)
        sessions = [d.date() for d in bdays]

    if not sessions:
        return []

    freq = str(frequency).lower()
    if freq.isdigit():
        step = max(1, int(freq))
        return sessions[MIN_HISTORY_BARS::step]

    if freq == "weekly":
        picked: list[date] = []
        for i, d in enumerate(sessions):
            if i < MIN_HISTORY_BARS:
                continue
            if not picked or (d - picked[-1]).days >= 5:
                picked.append(d)
        return picked

    if freq == "quarterly":
        picked: list[date] = []
        last_key: tuple[int, int] | None = None
        for d in sessions[MIN_HISTORY_BARS:]:
            key = (d.year, (d.month - 1) // 3)
            if key != last_key:
                picked.append(d)
                last_key = key
        return picked

    # monthly default
    picked = []
    last_key = None
    for d in sessions[MIN_HISTORY_BARS:]:
        key = (d.year, d.month)
        if key != last_key:
            picked.append(d)
            last_key = key
    return picked


def universe_for_date(sleeve: str, as_of: date, *, max_symbols: int) -> tuple[list[str], str]:
    """PIT-filtered universe or safe fallback."""
    base = [s.upper() for s in get_universe(sleeve)][: max(max_symbols * 2, 50)]
    if not base:
        base = ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "JPM", "V", "UNH", "XOM"]
    pit = active_symbols_on_date(base, as_of.isoformat())
    if pit and len(pit) >= min(5, max_symbols // 2):
        return pit[:max_symbols], "pit"
    return base[:max_symbols], "fallback"


def _rank_correlation(s: pd.Series, f: pd.Series) -> float:
    """Spearman rank IC with scipy-free fallback for offline tests."""
    try:
        return float(s.corr(f, method="spearman"))
    except (ImportError, ModuleNotFoundError, ValueError, TypeError):
        rs = s.rank(method="average")
        rf = f.rank(method="average")
        val = float(rs.corr(rf, method="pearson"))
        return 0.0 if np.isnan(val) else val


def cross_section_metrics(scores: list[float], forward_returns: list[float]) -> dict[str, Any]:
    """Rank IC, Pearson IC, hit rate, quintile stats."""
    if len(scores) < 5 or len(scores) != len(forward_returns):
        return {
            "sample_n": len(scores),
            "sufficient": False,
            "reason": "insufficient_cross_section",
        }

    s = pd.Series(scores, dtype=float)
    f = pd.Series(forward_returns, dtype=float)
    rank_ic = _rank_correlation(s, f)
    pearson_ic = float(s.corr(f, method="pearson"))
    if np.isnan(rank_ic):
        rank_ic = 0.0
    if np.isnan(pearson_ic):
        pearson_ic = 0.0

    hit_rate = float(np.mean((s > s.median()) == (f > 0)))
    top_quintile_avg = None
    spread = None
    try:
        df = pd.DataFrame({"score": s, "fwd": f})
        df["q"] = pd.qcut(df["score"], 5, labels=False, duplicates="drop")
        qm = df.groupby("q")["fwd"].mean()
        if len(qm) >= 2:
            top_quintile_avg = float(qm.iloc[-1])
            spread = float(qm.iloc[-1] - qm.iloc[0])
    except Exception:
        pass

    return {
        "sample_n": len(scores),
        "sufficient": True,
        "rank_ic": round(rank_ic, 4),
        "pearson_ic": round(pearson_ic, 4),
        "hit_rate": round(hit_rate, 4),
        "top_quintile_avg_return": round(top_quintile_avg, 6) if top_quintile_avg is not None else None,
        "top_minus_bottom_spread": round(spread, 6) if spread is not None else None,
    }


def turnover_rate(prev_top: set[str], curr_top: set[str]) -> float:
    """Fraction of names replaced in top quintile between rebalances."""
    if not prev_top and not curr_top:
        return 0.0
    if not prev_top or not curr_top:
        return 1.0
    kept = len(prev_top & curr_top)
    return round(1.0 - kept / max(len(curr_top), 1), 4)


def _top_quintile_symbols(scores: dict[str, float]) -> set[str]:
    if len(scores) < 5:
        return set(scores)
    s = pd.Series(scores)
    try:
        q = pd.qcut(s, 5, labels=False, duplicates="drop")
        top = s.index[q == q.max()].tolist()
        return {str(x) for x in top}
    except Exception:
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        k = max(1, len(ranked) // 5)
        return {sym for sym, _ in ranked[:k]}


def _forward_return_pct(hist: pd.DataFrame, as_of: date, horizon_sessions: int) -> float | None:
    from utils.trading_calendar import forward_return_sessions

    return forward_return_sessions(hist, as_of, horizon_sessions)


def _build_context(symbol: str, hist: pd.DataFrame, spy_hist: pd.DataFrame | None) -> CandidateContext | None:
    if hist.empty or len(hist) < MIN_HISTORY_BARS:
        return None
    price = float(hist["close"].iloc[-1])
    spy = None
    if spy_hist is not None and not spy_hist.empty:
        spy = spy_hist
    return CandidateContext(
        symbol=symbol.upper(),
        price=price,
        info={"sector": "Unknown"},
        fundamentals={},
        history=hist,
        spy_history=spy,
    )


def _score_symbol_as_of(
    symbol: str,
    sleeve: str,
    as_of: date,
    hist_full: pd.DataFrame,
    spy_full: pd.DataFrame | None,
) -> dict[str, Any] | None:
    """Score one symbol using ScoringEngine with history truncated to as_of."""
    hist = _truncate_history(hist_full, as_of)
    ctx = _build_context(symbol, hist, _truncate_history(spy_full, as_of) if spy_full is not None else None)
    if ctx is None:
        return None

    scoring = ScoringEngine.score(ctx, sleeve, quality_score=None, apply_openbb=False, metrics={})
    rets = simple_returns(hist["close"])
    risk = RiskEngine.assess(
        symbol,
        sleeve,
        final_score=scoring.final_score,
        apply_deduction=False,
        returns=rets,
    )
    factor_dicts = [
        {
            "factor_id": f.factor_id,
            "display_name": f.display_name,
            "norm_score": f.norm_score,
            "weight": f.weight,
            "contribution": f.contribution,
        }
        for f in scoring.factors
    ]
    weights = {f["factor_id"]: f["weight"] for f in factor_dicts}

    return {
        "symbol": symbol.upper(),
        "as_of_date": as_of.isoformat(),
        "score": scoring.final_score,
        "price": ctx.price,
        "factors": factor_dicts,
        "weights": weights,
        "attribution": {
            "raw_score": scoring.raw_score,
            "regime_mult": scoring.regime_mult,
            "sector_tilt": scoring.sector_tilt,
            "dq_multiplier": scoring.dq_multiplier,
            "final_score": scoring.final_score,
        },
        "risk_score": risk.risk_score,
        "risk_deduction_pts": risk.deduction_pts,
        "risk_breakdown": risk.breakdown,
    }


def _persist_research_snapshot(row: dict[str, Any], sleeve: str, *, horizon: int) -> int | None:
    from engines.prediction.snapshots import persist_prediction_snapshot

    snap_id = persist_prediction_snapshot(
        symbol=row["symbol"],
        sleeve=sleeve,
        price=row["price"],
        recommendation="research",
        confidence=min(100.0, max(0.0, row["score"])),
        time_horizon_days=horizon,
        alpha_score=row["score"],
        risk_score=row["risk_score"],
        data_confidence=None,
        market_regime=None,
        features={
            "as_of_date": row["as_of_date"],
            "factors": row["factors"],
            "attribution": row["attribution"],
            "weights": row["weights"],
            "risk_breakdown": row["risk_breakdown"],
        },
        thesis={"walk_forward": True},
        source="walk_forward_research",
    )
    try:
        persist_score_attribution(
            symbol=row["symbol"],
            sleeve=sleeve,
            raw_score=row["attribution"]["raw_score"],
            dq_multiplier=row["attribution"]["dq_multiplier"],
            risk_deduction=row["risk_deduction_pts"],
            regime_mult=row["attribution"]["regime_mult"],
            sector_tilt=row["attribution"]["sector_tilt"],
            final_score=row["score"],
            factors=row["factors"],
            weights=row["weights"],
            as_of_date=row["as_of_date"],
        )
        persist_risk_score(
            symbol=row["symbol"],
            sleeve=sleeve,
            risk_score=row["risk_score"],
            deduction_pts=row["risk_deduction_pts"],
            breakdown=row["risk_breakdown"],
            as_of_date=row["as_of_date"],
        )
    except Exception as exc:
        logger.debug("Attribution persist skipped for %s: %s", row["symbol"], exc)
    return snap_id


def persist_walk_forward_run(
    run_id: str,
    config: dict[str, Any],
    summary: dict[str, Any],
    *,
    started_at: datetime | None = None,
) -> None:
    engine = get_engine()
    from sqlalchemy.orm import Session

    with Session(engine) as session:
        existing = session.get(BacktestRun, run_id)
        payload = dict(
            run_id=run_id,
            run_type="walk_forward_research",
            config_json=json.dumps(config),
            metrics_json=json.dumps(summary),
            finished_at=_utcnow(),
        )
        if existing:
            for k, v in payload.items():
                setattr(existing, k, v)
        else:
            session.add(
                BacktestRun(
                    **payload,
                    started_at=started_at or _utcnow(),
                )
            )
        session.commit()
    from services.research_run_service import notify_run_persisted

    notify_run_persisted(run_id, store="backtest_runs")


def load_walk_forward_run(run_id: str) -> dict[str, Any] | None:
    from sqlalchemy.orm import Session

    engine = get_engine()
    with Session(engine) as session:
        row = session.get(BacktestRun, run_id)
        if not row:
            return None
        return {
            "run_id": row.run_id,
            "run_type": row.run_type,
            "config": json.loads(row.config_json or "{}"),
            "summary": json.loads(row.metrics_json or "{}"),
            "started_at": row.started_at.isoformat() if row.started_at else None,
            "finished_at": row.finished_at.isoformat() if row.finished_at else None,
        }


def run_walk_forward_research(
    config: WalkForwardConfig | dict[str, Any],
    *,
    price_panel: dict[str, pd.DataFrame] | None = None,
    spy_hist: pd.DataFrame | None = None,
) -> dict[str, Any]:
    """
    Execute walk-forward research. Does not update live factor weights.

    When price_panel is omitted, loads history via PriceService (live run).
    """
    if isinstance(config, dict):
        cfg = WalkForwardConfig(
            sleeve=config["sleeve"],
            start_date=config["start_date"],
            end_date=config["end_date"],
            rebalance_frequency=config.get("rebalance_frequency", "monthly"),
            forward_horizons=list(config.get("forward_horizons") or [20]),
            max_symbols=int(config.get("max_symbols") or DEFAULT_MAX_SYMBOLS),
            persist_snapshots=bool(config.get("persist_snapshots", True)),
        )
    else:
        cfg = config

    run_id = str(uuid.uuid4())
    started = _utcnow()
    dates = rebalance_dates(cfg.start_date, cfg.end_date, cfg.rebalance_frequency)
    end = _parse_date(cfg.end_date)
    max_horizon = max(cfg.forward_horizons) if cfg.forward_horizons else 20

    if price_panel is None:
        from data.price_service import PriceService

        ps = PriceService()
        universe_seed = [s.upper() for s in get_universe(cfg.sleeve)][: cfg.max_symbols]
        price_panel = {
            sym.upper(): df.reset_index(drop=True)
            for sym, df in ps.download_batch(universe_seed, period="5y").items()
            if df is not None and not df.empty
        }
        if spy_hist is None:
            spy_hist = ps.get_spy_history(period="5y").reset_index(drop=True)

    period_summaries: list[dict[str, Any]] = []
    horizon_agg: dict[int, list[dict[str, Any]]] = {h: [] for h in cfg.forward_horizons}
    snapshots_written = 0
    prev_top: set[str] = set()
    turnover_vals: list[float] = []

    for as_of in dates:
        symbols, uni_source = universe_for_date(cfg.sleeve, as_of, max_symbols=cfg.max_symbols)
        scored: list[dict[str, Any]] = []
        score_map: dict[str, float] = {}

        for sym in symbols:
            hist_full = price_panel.get(sym.upper())
            if hist_full is None or hist_full.empty:
                continue
            row = _score_symbol_as_of(sym, cfg.sleeve, as_of, hist_full, spy_hist)
            if row is None:
                continue
            scored.append(row)
            score_map[sym.upper()] = float(row["score"])

        if not scored:
            period_summaries.append(
                {
                    "as_of_date": as_of.isoformat(),
                    "universe_source": uni_source,
                    "symbols_scored": 0,
                    "skipped": True,
                }
            )
            continue

        curr_top = _top_quintile_symbols(score_map)
        if prev_top:
            turnover_vals.append(turnover_rate(prev_top, curr_top))
        prev_top = curr_top

        period_entry: dict[str, Any] = {
            "as_of_date": as_of.isoformat(),
            "universe_source": uni_source,
            "symbols_scored": len(scored),
            "horizons": {},
            "turnover": turnover_vals[-1] if turnover_vals else None,
        }

        for horizon in cfg.forward_horizons:
            scores: list[float] = []
            fwd_rets: list[float] = []
            for row in scored:
                sym = row["symbol"]
                hist_full = price_panel.get(sym.upper())
                if hist_full is None:
                    continue
                fwd_pct = _forward_return_pct(hist_full, as_of, horizon)
                if fwd_pct is None:
                    continue
                fwd = float(fwd_pct) / 100.0
                scores.append(float(row["score"]))
                fwd_rets.append(fwd)

            metrics = cross_section_metrics(scores, fwd_rets)
            period_entry["horizons"][str(horizon)] = metrics
            if metrics.get("sufficient"):
                horizon_agg[horizon].append(metrics)

        if cfg.persist_snapshots:
            primary_h = cfg.forward_horizons[0]
            for row in scored:
                snap_id = _persist_research_snapshot(row, cfg.sleeve, horizon=primary_h)
                if snap_id:
                    snapshots_written += 1

        period_summaries.append(period_entry)

    aggregate_horizons: dict[str, Any] = {}
    for h, rows in horizon_agg.items():
        if not rows:
            aggregate_horizons[str(h)] = {"sufficient": False, "periods": 0}
            continue
        aggregate_horizons[str(h)] = {
            "periods": len(rows),
            "mean_rank_ic": round(float(np.mean([r["rank_ic"] for r in rows])), 4),
            "mean_pearson_ic": round(float(np.mean([r["pearson_ic"] for r in rows])), 4),
            "mean_hit_rate": round(float(np.mean([r["hit_rate"] for r in rows])), 4),
            "mean_top_quintile_return": _safe_mean([r.get("top_quintile_avg_return") for r in rows]),
            "mean_spread": _safe_mean([r.get("top_minus_bottom_spread") for r in rows]),
        }

    summary = {
        "run_id": run_id,
        "status": "completed",
        "sleeve": cfg.sleeve,
        "start_date": cfg.start_date,
        "end_date": cfg.end_date,
        "rebalance_frequency": cfg.rebalance_frequency,
        "forward_horizons": cfg.forward_horizons,
        "rebalance_periods": len(dates),
        "periods_scored": sum(1 for p in period_summaries if not p.get("skipped")),
        "snapshots_written": snapshots_written,
        "mean_turnover": round(float(np.mean(turnover_vals)), 4) if turnover_vals else None,
        "aggregate_horizons": aggregate_horizons,
        "periods": period_summaries,
        "strategy_version": STRATEGY_VERSION,
        "factor_model_version": FACTOR_MODEL_VERSION,
        "weights_updated": False,
    }

    run_config = {
        "sleeve": cfg.sleeve,
        "start_date": cfg.start_date,
        "end_date": cfg.end_date,
        "rebalance_frequency": cfg.rebalance_frequency,
        "forward_horizons": cfg.forward_horizons,
        "max_symbols": cfg.max_symbols,
    }
    persist_walk_forward_run(run_id, run_config, summary, started_at=started)

    from engines.audit.logger import audit_log

    audit_log("walk_forward_research", sleeve=cfg.sleeve, payload={"run_id": run_id, "periods": len(dates)})

    return summary
