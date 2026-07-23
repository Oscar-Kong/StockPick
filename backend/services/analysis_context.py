"""Shared analysis context — one enrich/reconcile/history load for Workspace core."""
from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, TypeVar

import pandas as pd

from buckets import DEFAULT_BUCKET
from config import ANALYZE_RESULT_TTL, STRATEGY_VERSION
from data import cache as cache_module
from data.cache import Cache
from data.candidate_builder import build_candidate
from data.price_service import PriceService
from data.reconciler import DataReconciler, ReconcileResult
from models.schemas import Bucket
from screeners.compounder import CompounderScreener
from screeners.penny import PennyScreener
from services.scan_scoring import CandidateFeatures, prepare_candidate_features
from utils.datetime_util import utc_iso_z, utc_now
from utils.pydantic_util import json_safe, model_to_dict

logger = logging.getLogger(__name__)

_SCREENERS = {
    "penny": PennyScreener,
    "compounder": CompounderScreener,
}

_HISTORY_PERIOD = {
    "penny": "6mo",
    "compounder": "5y",
}

T = TypeVar("T")

_SINGLE_FLIGHT_LOCK = threading.Lock()
_SINGLE_FLIGHT: dict[str, Future] = {}
_SINGLE_FLIGHT_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="analysis-sf")


@dataclass
class AnalysisTimings:
    """Stage timings in milliseconds for Server-Timing / telemetry."""

    stages: dict[str, float] = field(default_factory=dict)

    def mark(self, name: str, started: float) -> None:
        self.stages[name] = round((time.perf_counter() - started) * 1000, 1)

    def server_timing_header(self) -> str:
        parts = [f"{k};dur={v:.1f}" for k, v in self.stages.items()]
        return ", ".join(parts)


@dataclass
class AnalysisContext:
    symbol: str
    sleeve: str
    ctx: Any  # CandidateContext
    reconcile: ReconcileResult | None
    features: CandidateFeatures
    hist_1y: pd.DataFrame
    spy_1y: pd.DataFrame
    price_meta: dict[str, Any]
    data_as_of: datetime
    timings: AnalysisTimings = field(default_factory=AnalysisTimings)
    deadline: float | None = None

    def remaining_seconds(self) -> float | None:
        if self.deadline is None:
            return None
        return max(0.0, self.deadline - time.monotonic())

    def timed_out(self) -> bool:
        rem = self.remaining_seconds()
        return rem is not None and rem <= 0


def _analysis_cache_key(symbol: str, bucket: str) -> str:
    return f"analyze:{symbol.upper()}:{bucket}"


def _core_cache_key(symbol: str, sleeve: str) -> str:
    return f"analyze:core:{symbol.upper()}:{sleeve}:{STRATEGY_VERSION}"


def single_flight(key: str, fn: Callable[[], T]) -> T:
    """Deduplicate concurrent identical analysis work."""
    with _SINGLE_FLIGHT_LOCK:
        existing = _SINGLE_FLIGHT.get(key)
        if existing is not None:
            fut = existing
            owned = False
        else:
            fut = _SINGLE_FLIGHT_EXECUTOR.submit(fn)
            _SINGLE_FLIGHT[key] = fut
            owned = True
    try:
        return fut.result()
    finally:
        if owned:
            with _SINGLE_FLIGHT_LOCK:
                if _SINGLE_FLIGHT.get(key) is fut:
                    del _SINGLE_FLIGHT[key]


def build_analysis_context(
    symbol: str,
    sleeve: str | None = None,
    *,
    force_refresh: bool = False,
    deadline: float | None = None,
    timings: AnalysisTimings | None = None,
) -> AnalysisContext | dict[str, Any]:
    """Build shared enrich + reconcile + history once."""
    timings = timings or AnalysisTimings()
    sym = symbol.upper()
    sleeve = sleeve or DEFAULT_BUCKET
    if sleeve not in _SCREENERS:
        return {"error": f"Invalid sleeve: {sleeve}"}

    if deadline is not None and time.monotonic() >= deadline:
        return {"error": "Analysis deadline exceeded before context build"}

    ps = PriceService()
    t0 = time.perf_counter()
    history_period = _HISTORY_PERIOD.get(sleeve, "1y")
    fundamentals_policy = "cache_first" if sleeve == "compounder" else "live"

    ctx = build_candidate(
        sym,
        history_period=history_period,
        reconcile=True,
        price_service=ps,
        fundamentals_policy=fundamentals_policy,
        include_spy=False,
    )
    timings.mark("candidate_build", t0)
    if ctx is None:
        return {"error": f"Could not load data for {sym}"}

    if deadline is not None and time.monotonic() >= deadline:
        return {"error": "Analysis deadline exceeded after candidate build"}

    t1 = time.perf_counter()
    quality = ctx.info.get("_reconcile_quality")
    rec: ReconcileResult | None = None
    if isinstance(ctx.info.get("_reconcile"), dict):
        # Rare path — prefer live reconcile for quality score
        pass
    from data.candidate_builder import _load_cached_fundamentals

    _cached_info, _cached_fund, cached_rec = _load_cached_fundamentals(sym)
    if cached_rec and cached_rec.quality_score > 0 and not force_refresh:
        rec = cached_rec
    else:
        try:
            rec = DataReconciler().reconcile(sym)
        except Exception as exc:
            logger.debug("Reconcile failed for %s: %s", sym, exc)
            rec = cached_rec
    timings.mark("fundamental_reconcile", t1)

    quality_score = float(rec.quality_score) if rec else (
        float(quality) if isinstance(quality, (int, float)) else None
    )

    t2 = time.perf_counter()
    hist_1y, price_meta = ps.get_history_with_meta(sym, period="1y", force_refresh=force_refresh)
    spy_1y, _spy_meta = ps.get_history_with_meta("SPY", period="1y", force_refresh=False)
    timings.mark("history_fetch", t2)

    bucket = Bucket(sleeve)
    t3 = time.perf_counter()
    features = prepare_candidate_features(
        ctx=ctx,
        bucket=bucket,
        symbol=sym,
        quality_score=quality_score,
    )
    timings.mark("feature_enrich", t3)

    return AnalysisContext(
        symbol=sym,
        sleeve=sleeve,
        ctx=ctx,
        reconcile=rec,
        features=features,
        hist_1y=hist_1y if hist_1y is not None else pd.DataFrame(),
        spy_1y=spy_1y if spy_1y is not None else pd.DataFrame(),
        price_meta=price_meta or {},
        data_as_of=utc_now(),
        timings=timings,
        deadline=deadline,
    )


def build_base_from_context(context: AnalysisContext) -> dict[str, Any]:
    """Assemble legacy AnalyzeSymbolResponse payload from shared context."""
    from services.alerts import compute_alerts
    from services.analyze_service import _quick_technicals_from_hist
    from services.scoring_facade import score_symbol_canonical

    if context.timed_out():
        return {"symbol": context.symbol, "error": "Analysis deadline exceeded"}

    t0 = time.perf_counter()
    bucket = Bucket(context.sleeve)
    screener = _SCREENERS[context.sleeve]()
    if hasattr(screener, "ps"):
        screener.ps = PriceService()

    quality = context.features.quality_score
    outcome = score_symbol_canonical(
        ctx=context.ctx,
        screener=screener,
        bucket=bucket,
        symbol=context.symbol,
        quality_score=quality,
    )
    context.timings.mark("base_score", t0)

    result = screener.to_result(
        context.ctx,
        outcome.score,
        outcome.signals,
        outcome.risk,
        outcome.summary,
        outcome.metrics,
    )

    rec = context.reconcile
    technicals = _quick_technicals_from_hist(context.hist_1y, context.spy_1y)
    metrics = result.metrics or {}
    alerts = compute_alerts(
        context.symbol,
        bucket=result.bucket.value,
        score=result.score,
        days_until_earnings=metrics.get("days_until_earnings"),
        valuation_warnings=result.valuation_warnings,
        data_quality_score=rec.quality_score if rec else None,
        reconcile_flags=rec.flags if rec else [],
        last_scanned_at=utc_iso_z(utc_now()),
        openbb_risk_flags=metrics.get("openbb_risk_flags"),
        openbb_governance_score=metrics.get("openbb_governance_score"),
    )

    ohlc = []
    hist = context.hist_1y
    if hist is not None and not hist.empty:
        for _, r in hist.tail(400).iterrows():
            ohlc.append(
                {
                    "date": r["date"].strftime("%Y-%m-%d")
                    if hasattr(r["date"], "strftime")
                    else str(r["date"])[:10],
                    "open": float(r["open"]),
                    "high": float(r["high"]),
                    "low": float(r["low"]),
                    "close": float(r["close"]),
                    "volume": float(r["volume"]),
                }
            )

    payload = {
        "symbol": context.symbol,
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
        "data_quality_score": rec.quality_score if rec else None,
        "reconcile": rec.to_dict() if rec else {},
        "technicals": technicals,
        "bucket_fit": {"scores": {}, "best_bucket": result.bucket.value},
        "alerts": alerts,
        "ohlc": ohlc,
        "fundamentals": {**(result.metrics or {}), **(rec.canonical if rec else {})},
        **(context.price_meta or {}),
    }
    Cache().set(
        _analysis_cache_key(context.symbol, bucket.value),
        json_safe(payload),
        ANALYZE_RESULT_TTL,
    )

    try:
        from services.quant_v2_service import maybe_persist_from_analysis

        maybe_persist_from_analysis(
            context.symbol,
            result.bucket.value,
            score=result.score,
            signals=payload["signals"],
            metrics=metrics,
            data_quality_score=rec.quality_score if rec else None,
            reconcile_flags=rec.flags if rec else [],
        )
    except Exception:
        pass

    return json_safe(payload)


def build_trade_plan(base: dict[str, Any], v2: Any) -> dict[str, Any]:
    """Derive a lightweight trade-plan card from base + v2 (no invented levels)."""
    sleeve = (getattr(v2, "sleeve", None) if v2 is not None else None) or base.get(
        "assigned_bucket", "penny"
    )
    rec = getattr(v2, "recommendation", None) if v2 is not None else None
    sizing = getattr(v2, "position_sizing", None) if v2 is not None else None
    price = base.get("price")
    metrics = base.get("metrics") or {}
    alerts = base.get("alerts") or []
    alert_msgs = [
        a.get("message") if isinstance(a, dict) else getattr(a, "message", None) for a in alerts
    ]
    alert_msgs = [m for m in alert_msgs if m]

    stop_pct = getattr(sizing, "stop_loss_pct", None) if sizing else None
    weight = getattr(sizing, "recommended_weight_pct", None) if sizing else None
    max_weight = getattr(sizing, "max_weight_pct", None) if sizing else None

    invalidation = []
    if rec and getattr(rec, "bear_case", None):
        invalidation.append(rec.bear_case)
    invalidation.extend(alert_msgs[:3])
    # Order-preserving dedupe — bear_case often duplicates an alert message.
    invalidation = list(dict.fromkeys(m for m in invalidation if m))

    plan: dict[str, Any] = {
        "sleeve": sleeve,
        "price": price,
        "invalidation": invalidation,
        "bull_case": getattr(rec, "bull_case", None) if rec else None,
        "bear_case": getattr(rec, "bear_case", None) if rec else None,
        "position_weight_pct": weight,
        "max_weight_pct": max_weight,
        "stop_loss_pct": stop_pct,
        "time_horizon_days": getattr(rec, "time_horizon_days", None) if rec else None,
        "expected_return_pct": getattr(rec, "expected_return_pct", None) if rec else None,
        "expected_downside_pct": getattr(rec, "expected_downside_pct", None) if rec else None,
        "liquidity_note": metrics.get("liquidity_note") or (getattr(v2, "metrics", {}) or {}).get(
            "liquidity_note"
        )
        if v2 is not None
        else metrics.get("liquidity_note"),
        "relative_volume": metrics.get("relative_volume") or metrics.get("rvol"),
        "avg_dollar_volume": metrics.get("avg_dollar_volume"),
        "atr_pct": metrics.get("atr_pct"),
        "spread_estimate": metrics.get("spread_estimate") or metrics.get("spread_pct"),
        "float": metrics.get("float") or metrics.get("floatShares"),
        "market_cap": metrics.get("market_cap") or (base.get("fundamentals") or {}).get("market_cap"),
        "data_confidence": None,
    }
    if rec and getattr(rec, "data_confidence", None):
        dc = rec.data_confidence
        plan["data_confidence"] = getattr(dc, "data_confidence", None)

    if sleeve == "penny":
        plan["max_hold_hint"] = "T+1 to T+3 typical for momentum sleeve"
        if price and stop_pct:
            plan["initial_stop"] = round(float(price) * (1 - float(stop_pct) / 100), 4)
        if price and getattr(rec, "expected_return_pct", None):
            er = float(rec.expected_return_pct)
            plan["target_1"] = round(float(price) * (1 + er / 200), 4)
            plan["target_2"] = round(float(price) * (1 + er / 100), 4)
            if stop_pct and stop_pct > 0:
                plan["risk_reward"] = round(abs(er) / float(stop_pct), 2)
    else:
        plan["max_hold_hint"] = "Multi-year accumulation sleeve"
        val = getattr(v2, "valuation", None) if v2 is not None else None
        if val:
            plan["fair_value"] = getattr(val, "dcf_fair_value", None)
            plan["fair_value_bull"] = getattr(val, "dcf_bull", None)
            plan["fair_value_bear"] = getattr(val, "dcf_bear", None)

    return plan


def build_analysis_delta(
    current_base: dict[str, Any],
    current_v2: Any,
    previous_saved: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Compare current analysis to previous saved analyze snapshot."""
    if not previous_saved:
        return None
    prev_payload = previous_saved.get("payload") or {}
    if not prev_payload:
        return None

    def _num(v: Any) -> float | None:
        try:
            if v is None:
                return None
            return float(v)
        except (TypeError, ValueError):
            return None

    cur_score = _num(getattr(current_v2, "score", None) if current_v2 is not None else None) or _num(
        current_base.get("score")
    )
    prev_score = _num(prev_payload.get("score"))
    cur_rec = None
    if current_v2 is not None and getattr(current_v2, "recommendation", None):
        cur_rec = current_v2.recommendation.recommendation
    prev_rec = (prev_payload.get("metrics") or {}).get("recommendation")

    changes = []
    if cur_score is not None and prev_score is not None and abs(cur_score - prev_score) >= 0.5:
        changes.append({"field": "score", "from": prev_score, "to": cur_score})
    if cur_rec and prev_rec and cur_rec != prev_rec:
        changes.append({"field": "recommendation", "from": prev_rec, "to": cur_rec})
    cur_risk = (
        getattr(current_v2, "risk_level", None) if current_v2 is not None else None
    ) or current_base.get("risk_level")
    prev_risk = prev_payload.get("risk_level")
    if cur_risk and prev_risk and cur_risk != prev_risk:
        changes.append({"field": "risk", "from": prev_risk, "to": cur_risk})
    cur_price = _num(current_base.get("price"))
    prev_price = _num(prev_payload.get("price"))
    if cur_price is not None and prev_price is not None and abs(cur_price - prev_price) / max(
        abs(prev_price), 1e-9
    ) >= 0.01:
        changes.append({"field": "price", "from": prev_price, "to": cur_price})

    main_change = None
    if changes:
        main_change = changes[0]["field"]
        if len(changes) > 1 and any(c["field"] == "recommendation" for c in changes):
            main_change = "recommendation"

    return {
        "previous_updated_at": previous_saved.get("updated_at"),
        "score": {"from": prev_score, "to": cur_score},
        "recommendation": {"from": prev_rec, "to": cur_rec},
        "risk": {"from": prev_risk, "to": cur_risk},
        "price": {"from": prev_price, "to": cur_price},
        "changes": changes,
        "main_change": main_change,
    }


def build_core_analysis(
    symbol: str,
    sleeve: str | None = None,
    *,
    force_refresh: bool = False,
    timeout_seconds: float | None = None,
    include_bucket_fit: bool = False,
) -> dict[str, Any]:
    """One shared context → base + v2 decision payload for Workspace."""
    from config import ANALYZE_ROUTE_TIMEOUT_SECONDS, SCORE_ENGINE_V2_ENABLED
    from services.quant_v2_service import build_v2_score
    from utils.pydantic_util import model_to_dict

    sleeve = sleeve or DEFAULT_BUCKET
    sym = symbol.upper()
    key = _core_cache_key(sym, sleeve)

    def _run() -> dict[str, Any]:
        timings = AnalysisTimings()
        t_cache = time.perf_counter()
        if not force_refresh:
            cached = Cache().get(key)
            if cached and not cached.get("error"):
                timings.mark("cache_lookup", t_cache)
                cached = dict(cached)
                cached["freshness"] = {
                    **(cached.get("freshness") or {}),
                    "status": "cached",
                    "served_from": "memory",
                }
                cached["timings_ms"] = timings.stages
                return cached
        timings.mark("cache_lookup", t_cache)

        deadline = None
        if timeout_seconds is not None:
            deadline = time.monotonic() + max(1.0, timeout_seconds)
        elif ANALYZE_ROUTE_TIMEOUT_SECONDS:
            deadline = time.monotonic() + max(1.0, float(ANALYZE_ROUTE_TIMEOUT_SECONDS))

        context = build_analysis_context(
            sym,
            sleeve,
            force_refresh=force_refresh,
            deadline=deadline,
            timings=timings,
        )
        if isinstance(context, dict) and context.get("error"):
            return context

        assert isinstance(context, AnalysisContext)
        base = build_base_from_context(context)
        if base.get("error"):
            return base

        v2_payload = None
        if SCORE_ENGINE_V2_ENABLED:
            t_v2 = time.perf_counter()
            v2_result = build_v2_score(
                sym,
                sleeve,
                validate_parity=False,
                persist_snapshot=False,
                include_sizing=True,
                analysis_context=context,
            )
            timings.mark("v2_score", t_v2)
            if not (isinstance(v2_result, dict) and v2_result.get("error")):
                v2_payload = v2_result

        if include_bucket_fit:
            from services.analyze_service import score_all_buckets

            t_bf = time.perf_counter()
            base["bucket_fit"] = score_all_buckets(sym)
            timings.mark("bucket_fit", t_bf)

        prev = cache_module.get_latest_saved_analyze(sym, sleeve)
        # Prefer previous snapshot that differs from what we are about to save
        delta = build_analysis_delta(base, v2_payload, prev)
        trade_plan = build_trade_plan(base, v2_payload)

        t_ser = time.perf_counter()
        v2_dict = None
        if v2_payload is not None:
            if hasattr(v2_payload, "dict"):
                v2_dict = model_to_dict(v2_payload)
            elif isinstance(v2_payload, dict):
                v2_dict = v2_payload

        freshness = {
            "status": "fresh",
            "data_as_of": utc_iso_z(context.data_as_of),
            "cached_at": utc_iso_z(utc_now()),
            "age_seconds": 0,
        }
        payload = json_safe(
            {
                "symbol": sym,
                "sleeve": sleeve,
                "base": base,
                "v2": v2_dict,
                "trade_plan": trade_plan,
                "delta": delta,
                "freshness": freshness,
                "timings_ms": timings.stages,
            }
        )
        timings.mark("serialization", t_ser)
        payload["timings_ms"] = timings.stages

        Cache().set(key, payload, ANALYZE_RESULT_TTL)
        try:
            cache_module.save_analyze_snapshot(symbol=sym, bucket=sleeve, payload=base)
        except Exception:
            pass
        return payload

    return single_flight(key if not force_refresh else f"{key}:refresh:{time.time()}", _run)


def build_analysis_snapshot(symbol: str, sleeve: str | None = None) -> dict[str, Any]:
    """Cached-first snapshot without recomputing pipelines."""
    sleeve = sleeve or DEFAULT_BUCKET
    sym = symbol.upper()
    timings = AnalysisTimings()
    t0 = time.perf_counter()

    core = Cache().get(_core_cache_key(sym, sleeve))
    if core and not core.get("error"):
        timings.mark("cache_lookup", t0)
        age = None
        cached_at = (core.get("freshness") or {}).get("cached_at")
        if cached_at:
            try:
                raw = str(cached_at).replace("Z", "+00:00")
                parsed = datetime.fromisoformat(raw)
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                age = max(0, int((datetime.now(timezone.utc) - parsed).total_seconds()))
            except Exception:
                age = None
        base = core.get("base") or {}
        # Slim OHLC for fast paint
        ohlc = list(base.get("ohlc") or [])[-90:]
        slim_base = {**base, "ohlc": ohlc}
        return json_safe(
            {
                "symbol": sym,
                "sleeve": sleeve,
                "base": slim_base,
                "v2": core.get("v2"),
                "trade_plan": core.get("trade_plan"),
                "delta": core.get("delta"),
                "freshness": {
                    "status": "cached",
                    "cached_at": cached_at,
                    "age_seconds": age,
                    "served_from": "memory_core",
                },
                "timings_ms": timings.stages,
                "stale": True,
            }
        )

    mem = Cache().get(_analysis_cache_key(sym, sleeve))
    if mem and not mem.get("error"):
        timings.mark("cache_lookup", t0)
        ohlc = list(mem.get("ohlc") or [])[-90:]
        return json_safe(
            {
                "symbol": sym,
                "sleeve": sleeve,
                "base": {**mem, "ohlc": ohlc},
                "v2": None,
                "trade_plan": None,
                "delta": None,
                "freshness": {
                    "status": "cached",
                    "served_from": "memory_analyze",
                },
                "timings_ms": timings.stages,
                "stale": True,
            }
        )

    saved = cache_module.get_latest_saved_analyze(sym, sleeve)
    timings.mark("cache_lookup", t0)
    if saved and saved.get("payload"):
        payload = saved["payload"]
        ohlc = list(payload.get("ohlc") or [])[-90:]
        return json_safe(
            {
                "symbol": sym,
                "sleeve": sleeve,
                "base": {**payload, "ohlc": ohlc},
                "v2": None,
                "trade_plan": None,
                "delta": None,
                "freshness": {
                    "status": "cached",
                    "cached_at": saved.get("updated_at"),
                    "served_from": "saved_analyze",
                },
                "timings_ms": timings.stages,
                "stale": True,
            }
        )

    return {
        "symbol": sym,
        "sleeve": sleeve,
        "base": None,
        "v2": None,
        "trade_plan": None,
        "delta": None,
        "freshness": {"status": "miss", "served_from": "none"},
        "timings_ms": timings.stages,
        "stale": True,
    }
