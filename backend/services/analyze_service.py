"""Analysis hub — watchlist matrix, full symbol analysis, compare, alerts."""
from __future__ import annotations

import logging
from utils.datetime_util import utc_iso_z, utc_now
from typing import Any

import pandas as pd

from data import cache as cache_module
from data.cache import Cache
from data.price_service import PERIOD_LIMIT, PriceService, _rows_to_dataframe
from data.candidate_builder import _load_cached_fundamentals
from data.reconciler import DataReconciler
from config import ANALYZE_RESULT_TTL
from models.schemas import Bucket, ScanOptions
from scoring.data_quality import adjust_score_for_data_quality
from scoring.technical import (
    breakout_score,
    relative_strength_vs_spy,
    trend_score,
)
from screeners.compounder import CompounderScreener
from screeners.penny import PennyScreener
from services.alerts import _is_stale, compute_alerts
from services.market_context import enrich_metrics
from services.watchlist_scanner import analyze_symbol
from utils.pydantic_util import json_safe, model_to_dict

logger = logging.getLogger(__name__)

_SCREENERS = {
    Bucket.penny: PennyScreener,
    Bucket.medium: PennyScreener,
    Bucket.compounder: CompounderScreener,
}


def _analysis_cache_key(symbol: str, bucket: Bucket) -> str:
    return f"analyze:{symbol.upper()}:{bucket.value}"


def get_cached_symbol_analysis(symbol: str, bucket: Bucket) -> dict[str, Any] | None:
    return Cache().get(_analysis_cache_key(symbol, bucket))


def _quick_technicals_from_hist(
    hist: pd.DataFrame,
    spy: pd.DataFrame | None = None,
) -> dict[str, Any]:
    if hist.empty:
        return {}
    close = float(hist["close"].iloc[-1])
    high_52 = float(hist["high"].max())
    low_52 = float(hist["low"].min())
    pct_from_high = ((close / high_52) - 1) * 100 if high_52 else 0
    rs = relative_strength_vs_spy(hist, spy, days=20) if spy is not None and not spy.empty else None
    return {
        "trend_score": round(trend_score(hist), 1),
        "breakout_score": round(breakout_score(hist), 1),
        "rs_vs_spy": round(rs, 1) if rs is not None else None,
        "pct_from_52w_high": round(pct_from_high, 1),
        "price": close,
    }


def _quick_technicals(symbol: str, ps: PriceService, *, db_only: bool = False) -> dict[str, Any]:
    if db_only:
        rows = ps.store.get_quotes(symbol.upper(), limit=PERIOD_LIMIT.get("1y", 280))
        hist = _rows_to_dataframe(rows)
        if len(hist) < 55:
            return {}
        spy_rows = ps.store.get_quotes("SPY", limit=280)
        spy = _rows_to_dataframe(spy_rows)
    else:
        hist = ps.get_history(symbol, period="1y")
        spy = ps.get_spy_history(period="1y")
    if hist.empty:
        return {}
    return _quick_technicals_from_hist(hist, spy)


def score_all_buckets(symbol: str, ps: PriceService | None = None) -> dict[str, Any]:
    """Score symbol under penny, medium, compounder (for bucket-fit)."""
    ps = ps or PriceService()
    scores: dict[str, Any] = {}
    for bucket in (Bucket.penny, Bucket.medium, Bucket.compounder):
        screener = _SCREENERS[bucket]()
        if hasattr(screener, "ps"):
            screener.ps = ps
        try:
            ctx = screener.enrich(symbol)
            if ctx is None:
                scores[bucket.value] = None
                continue
            passed = screener.hard_filter(ctx, ScanOptions())
            score, signals, risk, _, metrics = screener.score(ctx)
            q = ctx.info.get("_reconcile_quality")
            score = adjust_score_for_data_quality(score, q)
            scores[bucket.value] = {
                "score": round(score, 1),
                "passed_hard_filter": passed,
                "risk_level": risk.value,
                "top_signals": [
                    {"name": s.name, "value": round(s.value, 1)} for s in signals[:4]
                ],
            }
        except Exception as exc:
            logger.warning("Bucket score %s %s: %s", symbol, bucket, exc)
            scores[bucket.value] = None
    best = max(
        ((k, v["score"]) for k, v in scores.items() if v and v.get("score") is not None),
        key=lambda x: x[1],
        default=(None, None),
    )
    return {"scores": scores, "best_bucket": best[0]}


def build_symbol_analysis(
    symbol: str,
    bucket: Bucket | None = None,
    *,
    include_bucket_fit: bool = False,
    force_refresh: bool = False,
) -> dict[str, Any]:
    sym = symbol.upper()
    bucket = bucket or Bucket.penny
    ps = PriceService()

    result, error = analyze_symbol(sym, bucket)
    if error or result is None:
        return {"symbol": sym, "error": error or "Analysis failed"}

    cached_info, _cached_fund, cached_rec = _load_cached_fundamentals(sym)
    if cached_rec and cached_rec.quality_score > 0:
        rec = cached_rec
    else:
        rec = DataReconciler().reconcile(sym)

    hist, price_meta = ps.get_history_with_meta(sym, period="1y", force_refresh=force_refresh)
    spy, _spy_meta = ps.get_history_with_meta("SPY", period="1y", force_refresh=force_refresh)
    technicals = _quick_technicals_from_hist(hist, spy)
    if include_bucket_fit:
        bucket_fit = score_all_buckets(sym, ps)
    else:
        bucket_fit = {"scores": {}, "best_bucket": result.bucket.value}

    metrics = result.metrics or {}
    alerts = compute_alerts(
        sym,
        bucket=result.bucket.value,
        score=result.score,
        days_until_earnings=metrics.get("days_until_earnings"),
        valuation_warnings=result.valuation_warnings,
        data_quality_score=rec.quality_score,
        reconcile_flags=rec.flags,
        last_scanned_at=utc_iso_z(utc_now()),
        openbb_risk_flags=metrics.get("openbb_risk_flags"),
        openbb_governance_score=metrics.get("openbb_governance_score"),
    )

    ohlc = []
    if not hist.empty:
        for _, r in hist.tail(400).iterrows():
            ohlc.append(
                {
                    "date": r["date"].strftime("%Y-%m-%d"),
                    "open": float(r["open"]),
                    "high": float(r["high"]),
                    "low": float(r["low"]),
                    "close": float(r["close"]),
                    "volume": float(r["volume"]),
                }
            )

    payload = {
        "symbol": sym,
        "assigned_bucket": result.bucket.value,
        "price": result.price,
        "score": result.score,
        "risk_level": result.risk_level.value,
        "summary": result.summary,
        "signals": [model_to_dict(s) for s in result.signals],
        "metrics": metrics,
        "valuation_warnings": result.valuation_warnings,
        "earnings_date": result.earnings_date,
        "days_until_earnings": result.days_until_earnings,
        "earnings_soon": result.earnings_soon,
        "data_quality_score": rec.quality_score,
        "reconcile": rec.to_dict(),
        "technicals": technicals,
        "bucket_fit": bucket_fit,
        "alerts": alerts,
        "ohlc": ohlc,
        "fundamentals": {**result.metrics, **rec.canonical},
        **price_meta,
    }
    Cache().set(_analysis_cache_key(sym, bucket), json_safe(payload), ANALYZE_RESULT_TTL)

    try:
        from services.quant_v2_service import maybe_persist_from_analysis

        maybe_persist_from_analysis(
            sym,
            result.bucket.value,
            score=result.score,
            signals=payload["signals"],
            metrics=metrics,
            data_quality_score=rec.quality_score,
            reconcile_flags=rec.flags,
        )
    except Exception:
        pass

    return json_safe(payload)


def build_watchlist_matrix() -> list[dict[str, Any]]:
    items = cache_module.get_watchlist()
    ps = PriceService()
    rows: list[dict[str, Any]] = []

    for item in items:
        sym = item["symbol"]
        bucket = item.get("bucket", "medium")
        stale = _is_stale(item.get("last_scanned_at"))
        technicals = _quick_technicals(sym, ps, db_only=True)

        alerts = compute_alerts(
            sym,
            bucket=bucket,
            score=item.get("score"),
            days_until_earnings=item.get("days_until_earnings"),
            valuation_warnings=item.get("valuation_warnings"),
            data_quality_score=None,
            reconcile_flags=[],
            last_scanned_at=item.get("last_scanned_at"),
        )

        rows.append(
            {
                "symbol": sym,
                "bucket": bucket,
                "notes": item.get("notes", ""),
                "price": item.get("price"),
                "score": item.get("score"),
                "summary": item.get("summary", ""),
                "last_scanned_at": item.get("last_scanned_at"),
                "stale": stale,
                "earnings_date": item.get("earnings_date"),
                "days_until_earnings": item.get("days_until_earnings"),
                "valuation_warnings": item.get("valuation_warnings", []),
                "data_quality_score": None,
                "technicals": technicals,
                "alerts": alerts,
                "alert_count": len(alerts),
            }
        )

    rows.sort(key=lambda r: (-(r.get("alert_count") or 0), -(r.get("score") or 0)))
    return rows


def build_compare(symbols: list[str]) -> dict[str, Any]:
    """Side-by-side compare using watchlist cache + light metrics (not 3× full screener per symbol)."""
    syms = [s.upper() for s in symbols[:4]]
    if not syms:
        return {"symbols": [], "entries": [], "highlights": {}}

    ps = PriceService()
    watchlist_by_sym = {i["symbol"].upper(): i for i in cache_module.get_watchlist()}
    entries: list[dict[str, Any]] = []

    for sym in syms:
        try:
            wl = watchlist_by_sym.get(sym)
            rec = DataReconciler().reconcile(sym)
            technicals = _quick_technicals(sym, ps, db_only=bool(wl and wl.get("last_scanned_at")))

            entry: dict[str, Any] = {
                "symbol": sym,
                "assigned_bucket": wl.get("bucket") if wl else None,
                "price": wl.get("price") if wl else technicals.get("price"),
                "score": wl.get("score") if wl else None,
                "summary": (wl.get("summary") or wl.get("notes") or "") if wl else None,
                "risk_level": None,
                "passed_hard_filter": None,
                "reconcile_quality": rec.quality_score,
                "canonical": rec.canonical,
                "technicals": technicals,
                "alert_count": 0,
                "stale": _is_stale(wl.get("last_scanned_at")) if wl else False,
                "valuation_warnings": wl.get("valuation_warnings", []) if wl else [],
                "on_watchlist": bool(wl),
            }

            if wl:
                bucket = wl.get("bucket", "medium")
                alerts = compute_alerts(
                    sym,
                    bucket=bucket,
                    score=wl.get("score"),
                    days_until_earnings=wl.get("days_until_earnings"),
                    valuation_warnings=wl.get("valuation_warnings"),
                    data_quality_score=rec.quality_score,
                    reconcile_flags=rec.flags,
                    last_scanned_at=wl.get("last_scanned_at"),
                )
                entry["alert_count"] = len(alerts)
            elif not entry.get("score"):
                result, err = analyze_symbol(sym, "auto")
                if result:
                    entry["score"] = result.score
                    entry["assigned_bucket"] = result.bucket.value
                    entry["risk_level"] = result.risk_level.value
                    entry["summary"] = result.summary
                    entry["price"] = result.price
                    entry["passed_hard_filter"] = True
                elif err:
                    entry["error"] = err

            entries.append(entry)
        except Exception as exc:
            logger.warning("Compare failed for %s: %s", sym, exc)
            entries.append({"symbol": sym, "error": str(exc), "on_watchlist": False})

    highlights: dict[str, str | None] = {}
    scored = [e for e in entries if e.get("score") is not None and not e.get("error")]
    if scored:
        highlights["highest_score"] = max(scored, key=lambda e: e["score"])["symbol"]
    rs_rows = [
        e
        for e in entries
        if e.get("technicals", {}).get("rs_vs_spy") is not None and not e.get("error")
    ]
    if rs_rows:
        highlights["best_rs_vs_spy"] = max(
            rs_rows, key=lambda e: e["technicals"]["rs_vs_spy"]
        )["symbol"]
    qual_rows = [e for e in entries if e.get("reconcile_quality") is not None and not e.get("error")]
    if qual_rows:
        highlights["best_data_quality"] = max(
            qual_rows, key=lambda e: e["reconcile_quality"]
        )["symbol"]

    return {"symbols": syms, "entries": entries, "highlights": highlights}
