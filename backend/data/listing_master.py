"""Official Nasdaq/NYSE/AMEX listing master for universe validation."""
from __future__ import annotations

import logging
import re
import threading
import urllib.error
import urllib.request
from typing import TypedDict

from config import LISTING_MASTER_CACHE_TTL, LISTING_MASTER_FETCH_TIMEOUT
from utils.datetime_util import utc_iso_z, utc_now

logger = logging.getLogger(__name__)

NASDAQ_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"
OTHER_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt"

CACHE_KEY_SNAPSHOT = "universe:listing_master"
CACHE_KEY_REVISION = "universe:listing_master_revision"

_SUPPORTED_EXCHANGES = frozenset({"N", "A", "P", "Z", "V", "NASDAQ"})
_BAD_FINANCIAL_STATUS = frozenset({"D", "E", "Q", "G", "H", "J", "K"})
_EXCLUDED_NAME_PATTERNS = (
    " WARRANT",
    " WTS",
    " WT ",
    " UNIT",
    " UNITS",
    " RIGHT",
    " RIGHTS",
    " PFD",
    " PREF",
    " PREFERRED",
    " DEP SHS",
    "%",
    "CLOSED END FUND",
    "CLOSED-END FUND",
)

_refresh_lock = threading.Lock()
_refresh_in_progress = False


class ListingRecord(TypedDict):
    symbol: str
    security_name: str
    exchange: str
    is_etf: bool
    is_test_issue: bool
    financial_status: str | None
    security_type: str | None


def _canonical_symbol(raw: str) -> str:
    """Normalize exchange symbol to the app's canonical form (class shares use dash)."""
    sym = (raw or "").strip().upper()
    if not sym:
        return ""
    return sym.replace(".", "-")


def _is_excluded_security(name: str, symbol: str) -> bool:
    upper = (name or "").upper()
    if any(p in upper for p in _EXCLUDED_NAME_PATTERNS):
        return True
    if len(symbol) >= 5 and symbol[-1] in "WUR":
        if " ACQUISITION" in upper or " SPAC" in upper:
            return True
    return False


def _record_is_eligible(rec: ListingRecord) -> bool:
    if rec["is_test_issue"] or rec["is_etf"]:
        return False
    fin = rec.get("financial_status")
    if fin and fin in _BAD_FINANCIAL_STATUS:
        return False
    exchange = (rec.get("exchange") or "").upper()
    if exchange and exchange not in _SUPPORTED_EXCHANGES and exchange != "NASDAQ":
        return False
    if _is_excluded_security(rec["security_name"], rec["symbol"]):
        return False
    return True


def parse_nasdaq_listed(text: str) -> dict[str, ListingRecord]:
    records: dict[str, ListingRecord] = {}
    for line in text.strip().splitlines()[1:]:
        if not line or line.startswith("File Created"):
            continue
        parts = line.split("|")
        if len(parts) < 8:
            continue
        raw_sym, name, _mkt, test, fin, _lot, etf, _nextsh = parts[:8]
        sym = _canonical_symbol(raw_sym)
        if not sym:
            continue
        records[sym] = ListingRecord(
            symbol=sym,
            security_name=name,
            exchange="NASDAQ",
            is_etf=etf.strip().upper() == "Y",
            is_test_issue=test.strip().upper() == "Y",
            financial_status=fin.strip().upper() if fin.strip().upper() not in ("N", "") else None,
            security_type=None,
        )
    return records


def parse_other_listed(text: str) -> dict[str, ListingRecord]:
    records: dict[str, ListingRecord] = {}
    for line in text.strip().splitlines()[1:]:
        if not line or line.startswith("File Created"):
            continue
        parts = line.split("|")
        if len(parts) < 7:
            continue
        raw_sym, name, exchange, _cqs, etf, _lot, test = parts[:7]
        sym = _canonical_symbol(raw_sym)
        if not sym:
            continue
        records[sym] = ListingRecord(
            symbol=sym,
            security_name=name,
            exchange=exchange.strip().upper(),
            is_etf=etf.strip().upper() == "Y",
            is_test_issue=test.strip().upper() == "Y",
            financial_status=None,
            security_type=None,
        )
    return records


def parse_listing_files(*, nasdaq_text: str, other_text: str) -> dict[str, ListingRecord]:
    merged: dict[str, ListingRecord] = {}
    merged.update(parse_nasdaq_listed(nasdaq_text))
    merged.update(parse_other_listed(other_text))
    return merged


def active_equity_symbols(records: dict[str, ListingRecord]) -> set[str]:
    return {sym for sym, rec in records.items() if _record_is_eligible(rec)}


def _fetch_url(url: str, *, timeout: float) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "StockPicker/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _load_cached_snapshot() -> dict | None:
    try:
        from data.cache import Cache

        return Cache().get(CACHE_KEY_SNAPSHOT)
    except Exception as exc:
        logger.debug("Listing master cache read failed: %s", exc)
        return None


def get_listing_revision() -> str | None:
    try:
        from data.cache import Cache

        data = Cache().get(CACHE_KEY_REVISION)
        if data and data.get("revision"):
            return str(data["revision"])
    except Exception:
        pass
    snap = _load_cached_snapshot()
    if snap and snap.get("updated_at"):
        return str(snap["updated_at"])
    return None


def get_active_listing_symbols() -> set[str] | None:
    """Return cached active equity symbols, or None when no snapshot exists."""
    snap = _load_cached_snapshot()
    if not snap or not snap.get("symbols"):
        return None
    return {str(s).upper() for s in snap["symbols"]}


def _save_snapshot(symbols: set[str], *, source: str) -> str:
    from data.cache import Cache

    updated_at = utc_iso_z(utc_now())
    revision = re.sub(r"[^0-9A-Za-z._-]", "-", updated_at)
    snapshot = {
        "symbols": sorted(symbols),
        "updated_at": updated_at,
        "source": source,
        "record_count": len(symbols),
    }
    cache = Cache()
    cache.set(CACHE_KEY_SNAPSHOT, snapshot, ttl_seconds=LISTING_MASTER_CACHE_TTL)
    cache.set(
        CACHE_KEY_REVISION,
        {"revision": revision, "updated_at": updated_at},
        ttl_seconds=LISTING_MASTER_CACHE_TTL,
    )
    return revision


def refresh_listing_master(*, force: bool = False) -> dict:
    """Fetch official listings and persist an active-equity snapshot.

    Uses stale-while-revalidate: on failure, returns the last cached snapshot
    without deleting it.
    """
    global _refresh_in_progress

    with _refresh_lock:
        if _refresh_in_progress and not force:
            return {"status": "skipped", "reason": "refresh_in_progress"}
        _refresh_in_progress = True

    try:
        nasdaq_text = _fetch_url(NASDAQ_LISTED_URL, timeout=LISTING_MASTER_FETCH_TIMEOUT)
        other_text = _fetch_url(OTHER_LISTED_URL, timeout=LISTING_MASTER_FETCH_TIMEOUT)
        records = parse_listing_files(nasdaq_text=nasdaq_text, other_text=other_text)
        symbols = active_equity_symbols(records)
        if not symbols:
            raise ValueError("Parsed listing master contained zero eligible symbols")
        revision = _save_snapshot(symbols, source="nasdaqtrader")
        logger.info(
            "Listing master refreshed: %s active equities (revision=%s)",
            len(symbols),
            revision,
        )
        return {
            "status": "ok",
            "symbol_count": len(symbols),
            "revision": revision,
            "source": "nasdaqtrader",
        }
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        logger.warning("Listing master refresh failed: %s", exc)
        cached = _load_cached_snapshot()
        if cached and cached.get("symbols"):
            return {
                "status": "stale",
                "error": str(exc)[:200],
                "symbol_count": len(cached["symbols"]),
                "updated_at": cached.get("updated_at"),
            }
        return {"status": "failed", "error": str(exc)[:200]}
    finally:
        with _refresh_lock:
            _refresh_in_progress = False


def refresh_listing_master_async(*, force: bool = False) -> None:
    """Non-blocking refresh for startup hooks."""

    def _run() -> None:
        try:
            refresh_listing_master(force=force)
        except Exception as exc:
            logger.warning("Background listing master refresh failed: %s", exc)

    thread = threading.Thread(target=_run, name="listing-master-refresh", daemon=True)
    thread.start()
