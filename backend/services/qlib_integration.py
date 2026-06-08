"""Qlib alpha integration scaffold.

Current phase provides a stable API contract with rule-based proxy scores.
Later phases can replace `_proxy_alpha_from_scan` with offline Qlib predictions.
"""
from __future__ import annotations

from datetime import datetime, timezone

from config import QLIB_ENABLED
from data.cache import Cache
from models.schemas import Bucket

_CACHE_KEY_TMPL = "ml:alpha:latest:{bucket}"
_PRED_KEY_TMPL = "ml:alpha:pred:{bucket}:{symbol}"
_CACHE_TTL_SECONDS = 86400


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat()


def _proxy_alpha_from_scan(bucket: Bucket) -> list[dict]:
    cache = Cache()
    latest = cache.get(f"scan:latest:{bucket.value}") or {}
    rows = latest.get("results") or []
    ranked = sorted(rows, key=lambda r: float(r.get("score") or 0), reverse=True)[:20]
    items = []
    for i, row in enumerate(ranked, start=1):
        score = float(row.get("score") or 0)
        alpha = round(min(1.0, max(0.0, score / 100.0)), 4)
        items.append(
            {
                "symbol": row.get("symbol", ""),
                "alpha_score": alpha,
                "rank": i,
                "source": "rule_proxy",
            }
        )
    return items


def get_latest_alpha(bucket: Bucket) -> dict:
    cache = Cache()
    key = _CACHE_KEY_TMPL.format(bucket=bucket.value)
    cached = cache.get(key)
    if cached:
        return cached

    items = _proxy_alpha_from_scan(bucket)
    payload = {
        "bucket": bucket.value,
        "as_of": _utcnow_iso(),
        "model_name": "qlib_alpha",
        "model_version": "proxy-v0",
        "enabled": bool(QLIB_ENABLED),
        "items": items,
        "notes": [
            "Using rule-proxy alpha until offline Qlib predictions are connected.",
            "Set QLIB_ENABLED=true once model artifacts are available.",
        ],
    }
    cache.set(key, payload, _CACHE_TTL_SECONDS)
    return payload


def get_symbol_alpha_score(bucket: Bucket, symbol: str, fallback_score_0_100: float) -> tuple[float, str]:
    """Return alpha score in 0-100 range and source label."""
    cache = Cache()
    sym = symbol.strip().upper()
    pred = cache.get(_PRED_KEY_TMPL.format(bucket=bucket.value, symbol=sym)) or {}
    pred_score = pred.get("alpha_score")
    if pred_score is not None:
        try:
            raw = float(pred_score)
            if 0 <= raw <= 1:
                return round(raw * 100, 2), "qlib_offline"
            return round(max(0.0, min(100.0, raw)), 2), "qlib_offline"
        except Exception:
            pass

    latest = get_latest_alpha(bucket)
    for row in latest.get("items", []):
        if str(row.get("symbol", "")).upper() == sym:
            try:
                raw = float(row.get("alpha_score", 0))
                if 0 <= raw <= 1:
                    return round(raw * 100, 2), str(row.get("source", "rule_proxy"))
                return round(max(0.0, min(100.0, raw)), 2), str(row.get("source", "rule_proxy"))
            except Exception:
                break

    return round(max(0.0, min(100.0, fallback_score_0_100)), 2), "rule_proxy"


def ingest_alpha_predictions(
    bucket: Bucket,
    as_of: str,
    model_version: str,
    items: list[dict],
) -> dict:
    """Store offline Qlib predictions for runtime lookup."""
    cache = Cache()
    norm_items: list[dict] = []
    for i, row in enumerate(items, start=1):
        sym = str(row.get("symbol", "")).strip().upper()
        if not sym:
            continue
        alpha_raw = float(row.get("alpha_score", 0))
        alpha_norm = max(0.0, min(1.0, alpha_raw if alpha_raw <= 1 else alpha_raw / 100.0))
        rec = {
            "symbol": sym,
            "alpha_score": round(alpha_norm, 6),
            "rank": int(row.get("rank") or i),
            "source": "qlib_offline",
        }
        norm_items.append(rec)
        cache.set(
            _PRED_KEY_TMPL.format(bucket=bucket.value, symbol=sym),
            {
                "symbol": sym,
                "alpha_score": rec["alpha_score"],
                "as_of": as_of,
                "model_version": model_version,
            },
            _CACHE_TTL_SECONDS * 7,
        )

    norm_items.sort(key=lambda x: x.get("rank", 999999))
    payload = {
        "bucket": bucket.value,
        "as_of": as_of or _utcnow_iso(),
        "model_name": "qlib_alpha",
        "model_version": model_version,
        "enabled": True,
        "items": norm_items,
        "notes": ["Offline Qlib predictions ingested via API."],
    }
    cache.set(_CACHE_KEY_TMPL.format(bucket=bucket.value), payload, _CACHE_TTL_SECONDS * 7)
    return payload

