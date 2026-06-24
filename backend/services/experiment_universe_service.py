"""Resolve stock universes for experiment studio — all sources return equities only."""
from __future__ import annotations

import logging
from typing import Any

from buckets import DEFAULT_BUCKET
from data.universe import get_universe

logger = logging.getLogger(__name__)

VALID_SOURCES = frozenset(
    {
        "latest_scan",
        "saved_scan",
        "watchlist",
        "portfolio_holdings",
        "full_bucket",
        "custom_symbols",
    }
)


def _normalize_symbols(symbols: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for s in symbols:
        sym = str(s).upper().strip()
        if sym and sym not in seen:
            seen.add(sym)
            out.append(sym)
    return out


def resolve_universe(
    universe_definition: dict[str, Any] | None,
    *,
    sleeve: str | None = None,
    parameters: dict[str, Any] | None = None,
) -> tuple[list[str], str, list[str]]:
    """
    Returns (symbols, source_label, warnings).
    """
    universe_definition = universe_definition or {}
    parameters = parameters or {}
    warnings: list[str] = []
    source = str(universe_definition.get("source") or parameters.get("universe_source") or "full_bucket")
    if source not in VALID_SOURCES:
        warnings.append(f"unknown universe source '{source}', falling back to full_bucket")
        source = "full_bucket"

    max_symbols = int(parameters.get("max_symbols") or universe_definition.get("max_symbols") or 30)
    bucket = sleeve or DEFAULT_BUCKET

    if source == "custom_symbols":
        raw = universe_definition.get("symbols") or parameters.get("symbols") or parameters.get("custom_symbols") or []
        if isinstance(raw, str):
            raw = [x.strip() for x in raw.replace(",", " ").split() if x.strip()]
        symbols = _normalize_symbols(list(raw))[:max_symbols]
        return symbols, "custom_symbols", warnings

    if source == "latest_scan":
        try:
            from services.scan_manager import scan_manager
            from buckets import Bucket

            data = scan_manager.get_latest_scan(Bucket(bucket))
            rows = (data or {}).get("results") or (data or {}).get("stocks") or []
            symbols = _normalize_symbols(
                [str(r.get("symbol") or r.get("ticker") or "") for r in rows if isinstance(r, dict)]
            )[:max_symbols]
            if not symbols:
                warnings.append("latest scan empty — falling back to bucket universe")
            else:
                return symbols, "latest_scan", warnings
        except Exception as exc:
            logger.debug("latest_scan resolve failed: %s", exc)
            warnings.append("latest scan unavailable")

    if source == "saved_scan":
        scan_id = universe_definition.get("scan_id") or parameters.get("scan_id")
        try:
            from data import cache as cache_module

            if scan_id is not None:
                row = cache_module.get_saved_scan(int(scan_id))
            else:
                rows = cache_module.list_saved_scans(bucket=bucket, limit=1)
                row = rows[0] if rows else None
            if row:
                payload = row.get("payload") or row.get("data") or {}
                stocks = payload.get("results") or payload.get("stocks") or []
                symbols = _normalize_symbols(
                    [str(r.get("symbol") or "") for r in stocks if isinstance(r, dict)]
                )[:max_symbols]
                if symbols:
                    return symbols, "saved_scan", warnings
            warnings.append("saved scan empty or missing")
        except Exception as exc:
            logger.debug("saved_scan resolve failed: %s", exc)
            warnings.append("saved scan unavailable")

    if source == "watchlist":
        try:
            from data import cache as cache_module

            rows = cache_module.get_watchlist()
            symbols = _normalize_symbols([str(r.get("symbol") or "") for r in rows])[:max_symbols]
            if symbols:
                return symbols, "watchlist", warnings
            warnings.append("watchlist empty")
        except Exception as exc:
            logger.debug("watchlist resolve failed: %s", exc)
            warnings.append("watchlist unavailable")

    if source == "portfolio_holdings":
        try:
            from services.holdings_loader import load_holdings

            symbols, src = load_holdings()
            symbols = _normalize_symbols(symbols)[:max_symbols]
            if symbols:
                return symbols, src, warnings
            warnings.append("no portfolio holdings found")
        except Exception as exc:
            logger.debug("holdings resolve failed: %s", exc)
            warnings.append("portfolio holdings unavailable")

    # full_bucket fallback
    try:
        symbols = _normalize_symbols(get_universe(bucket))[:max_symbols]
        if symbols:
            return symbols, "full_bucket", warnings
    except Exception as exc:
        logger.debug("bucket universe failed: %s", exc)
        warnings.append("bucket universe unavailable")

    return [], source, warnings
