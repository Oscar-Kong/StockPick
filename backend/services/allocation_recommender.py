"""FinRL allocation scaffold with safe heuristic fallback."""
from __future__ import annotations

from datetime import datetime, timezone

from config import FINRL_ENABLED
from data.cache import Cache, get_watchlist
from models.schemas import Bucket
from services.portfolio_optimizer import optimize_portfolio


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat()


def _default_symbols(bucket: Bucket) -> list[str]:
    cache = Cache()
    latest = cache.get(f"scan:latest:{bucket.value}") or {}
    results = latest.get("results") or []
    scan_symbols = [str(r.get("symbol", "")).upper() for r in results if r.get("symbol")]
    scan_symbols = [s for s in scan_symbols if s][:10]
    if scan_symbols:
        return list(dict.fromkeys(scan_symbols))

    wl = get_watchlist()
    wl_symbols = [str(r.get("symbol", "")).upper() for r in wl if str(r.get("bucket", "")).lower() == bucket.value]
    wl_symbols = [s for s in wl_symbols if s][:10]
    return list(dict.fromkeys(wl_symbols))


def get_allocation_recommendation(bucket: Bucket, symbols: list[str] | None = None) -> dict:
    chosen = [s.strip().upper() for s in (symbols or []) if s and s.strip()]
    chosen = list(dict.fromkeys(chosen))
    if not chosen:
        chosen = _default_symbols(bucket)

    if len(chosen) < 2:
        return {
            "bucket": bucket.value,
            "as_of": _utcnow_iso(),
            "model_name": "finrl_allocator",
            "model_version": "heuristic-v0",
            "enabled": bool(FINRL_ENABLED),
            "source": "heuristic",
            "symbols_used": chosen,
            "excluded": [],
            "target_weights": [],
            "constraints": {"max_weight": 0.30, "cash_buffer": 0.05, "long_only": True},
            "notes": ["Need at least 2 symbols from latest scan/watchlist to generate allocation."],
        }

    opt = optimize_portfolio(
        chosen,
        objective="min_vol",
        max_weight=0.30,
        cash_buffer=0.05,
        lookback_period="1y",
    )

    # For now, confidence is derived from final normalized weight.
    target_weights = [
        {
            "symbol": s,
            "target_weight": float(w),
            "score": None,
            "confidence": round(min(1.0, max(0.0, float(w) * 2.5)), 4),
        }
        for s, w in sorted(opt.weights.items(), key=lambda kv: kv[1], reverse=True)
    ]

    notes = opt.notes or []
    if FINRL_ENABLED:
        notes = notes + ["FinRL flag enabled; using heuristic allocator until trained policy is wired."]
    else:
        notes = notes + ["FINRL_ENABLED=false; heuristic allocator in use."]

    return {
        "bucket": bucket.value,
        "as_of": _utcnow_iso(),
        "model_name": "finrl_allocator",
        "model_version": "heuristic-v0",
        "enabled": bool(FINRL_ENABLED),
        "source": "heuristic",
        "symbols_used": opt.symbols_used,
        "excluded": opt.excluded,
        "target_weights": target_weights,
        "constraints": {
            "max_weight": 0.30,
            "cash_buffer": 0.05,
            "long_only": True,
            "objective": "min_vol",
        },
        "notes": notes,
    }

