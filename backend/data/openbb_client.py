"""OpenBB Platform bridge — fundamentals reconciliation, macro, SEC / insider risk.

Enable: OPENBB_ENABLED=true and pip install -r requirements-openbb.txt
Keys are synced from the project .env (FMP, FRED, Alpha Vantage, Nasdaq).
Finnhub / NewsAPI remain on custom clients (no OpenBB provider).
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from dataclasses import dataclass, field
from typing import Any

from config import (
    ALPHA_VANTAGE_API_KEY,
    FMP_API_KEY,
    FRED_API_KEY,
    NASDAQ_DATA_LINK_API_KEY,
    OPENBB_ENABLED,
    OPENBB_INSIDER_ON_RISK,
    OPENBB_RISK_CACHE_TTL,
)

logger = logging.getLogger(__name__)

_obb: Any | None = None
_configured = False
_openbb_import_ok: bool | None = None

# FRED series used for compounder macro regime (same logic as FredClient)
_MACRO_SERIES = ("FEDFUNDS", "UNRATE", "DGS10")

# High-impact SEC forms for swing / long-term holders
_RISK_FORMS = frozenset({"8-K", "10-K", "10-Q", "S-1", "S-3", "424B", "6-K"})


@dataclass
class OpenBBRiskSnapshot:
    governance_score: float = 70.0
    warnings: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    recent_filings: list[dict[str, Any]] = field(default_factory=list)
    insider_sell_ratio: float | None = None


def is_available() -> bool:
    """True if OpenBB is enabled and import succeeded (may still be loading on first boot)."""
    if not OPENBB_ENABLED:
        return False
    if _openbb_import_ok is True:
        return True
    if _openbb_import_ok is False:
        return False
    try:
        _get_obb()
        return True
    except Exception:
        return False


def openbb_ready() -> bool:
    """Non-blocking readiness check (set after background warmup)."""
    return _openbb_import_ok is True


def warmup_openbb() -> None:
    """Import OpenBB once (can take 10–30s first time). Call from a background thread."""
    global _openbb_import_ok
    if not OPENBB_ENABLED:
        _openbb_import_ok = False
        return
    try:
        _get_obb()
        _openbb_import_ok = True
        logger.info("OpenBB Platform ready")
    except Exception as exc:
        _openbb_import_ok = False
        logger.warning("OpenBB warmup failed: %s", exc)


def _get_obb():
    global _obb, _configured, _openbb_import_ok
    if _obb is not None:
        if not _configured:
            _apply_credentials(_obb)
        return _obb
    from openbb import obb

    _obb = obb
    _apply_credentials(_obb)
    _openbb_import_ok = True
    return _obb


def _apply_credentials(obb: Any) -> None:
    global _configured
    creds = obb.user.credentials
    mapping = {
        "fmp_api_key": FMP_API_KEY,
        "fred_api_key": FRED_API_KEY,
        "alpha_vantage_api_key": ALPHA_VANTAGE_API_KEY,
        "nasdaq_api_key": NASDAQ_DATA_LINK_API_KEY,
    }
    for attr, value in mapping.items():
        if value and hasattr(creds, attr):
            setattr(creds, attr, value)
    _configured = True


def _to_records(result: Any) -> list[dict[str, Any]]:
    if result is None:
        return []
    try:
        df = result.to_dataframe()
        if df is None or df.empty:
            return []
        df = df.reset_index()
        return df.to_dict(orient="records")
    except Exception as exc:
        logger.debug("OpenBB to_dataframe failed: %s", exc)
        return []


def _pick(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in row and row[key] is not None:
            return row[key]
    return None


def _to_float(val: Any) -> float | None:
    if val is None:
        return None
    try:
        f = float(val)
        return f if f == f else None
    except (TypeError, ValueError):
        return None


def normalize_fundamentals_row(row: dict[str, Any]) -> dict[str, Any]:
    """Map OpenBB standard / FMP metrics into Stock Picker field names."""
    price = _to_float(_pick(row, "price", "close", "last_price"))
    pe = _to_float(_pick(row, "pe_ratio", "trailing_pe", "peRatioTTM", "price_to_earnings_ratio"))
    roe = _to_float(_pick(row, "return_on_equity", "roe", "returnOnEquityTTM"))
    margin = _to_float(
        _pick(row, "net_profit_margin", "profit_margin", "netProfitMarginTTM", "profitMargins")
    )
    mcap = _to_float(_pick(row, "market_cap", "marketCap", "market_capitalization"))
    revenue = _to_float(_pick(row, "revenue", "total_revenue", "revenue_per_share"))

    out: dict[str, Any] = {"source": "openbb"}
    if price is not None:
        out["currentPrice"] = out["price"] = price
    if pe is not None:
        out["trailingPE"] = out["pe_ratio"] = pe
    if roe is not None:
        out["returnOnEquity"] = out["roe"] = roe
    if margin is not None:
        out["profitMargins"] = out["profit_margin"] = margin
    if mcap is not None:
        out["marketCap"] = out["market_cap"] = mcap
    if revenue is not None:
        out["totalRevenue"] = out["revenue"] = revenue
    for meta in ("sector", "industry", "symbol", "name", "beta"):
        v = _pick(row, meta)
        if v is not None:
            out[meta] = v
    return out


def fetch_fundamentals_for_reconcile(symbol: str) -> dict[str, Any]:
    """Normalized fundamentals dict for DataReconciler (source key: openbb)."""
    if not is_available():
        return {}
    raw = get_key_metrics(symbol)
    if not raw:
        return {}
    return normalize_fundamentals_row(raw)


def get_key_metrics(symbol: str) -> dict[str, Any]:
    obb = _get_obb()
    sym = symbol.upper()
    if FMP_API_KEY:
        try:
            out = obb.equity.fundamental.metrics(symbol=sym, provider="fmp")
            rows = _to_records(out)
            if rows:
                return rows[0]
        except Exception as exc:
            logger.debug("OpenBB fmp metrics %s: %s", sym, exc)
    try:
        out = obb.equity.profile(symbol=sym, provider="fmp")
        rows = _to_records(out)
        return rows[0] if rows else {}
    except Exception as exc:
        logger.debug("OpenBB fallback profile %s: %s", sym, exc)
        return {}


def get_fred_latest(series_id: str) -> float | None:
    obb = _get_obb()
    try:
        out = obb.economy.fred_series(symbol=series_id, provider="fred")
        rows = _to_records(out)
        for row in reversed(rows):
            val = row.get("value")
            if val is not None and str(val) not in (".", ""):
                return float(val)
    except Exception as exc:
        logger.debug("OpenBB FRED %s: %s", series_id, exc)
    return None


def macro_regime_score() -> float | None:
    """Same heuristic as FredClient; returns None if OpenBB/FRED unavailable."""
    if not is_available() or not FRED_API_KEY:
        return None

    fed_funds = get_fred_latest("FEDFUNDS")
    unemployment = get_fred_latest("UNRATE")
    treasury_10y = get_fred_latest("DGS10")

    score = 50.0
    if fed_funds is not None and fed_funds < 4.0:
        score += 10
    elif fed_funds is not None and fed_funds > 5.0:
        score -= 10

    if unemployment is not None and unemployment < 5.0:
        score += 10
    elif unemployment is not None and unemployment > 6.0:
        score -= 10

    if treasury_10y is not None and 3.0 <= treasury_10y <= 5.0:
        score += 5

    return max(0.0, min(100.0, score))


def get_sec_filings(symbol: str, limit: int = 8) -> list[dict[str, Any]]:
    obb = _get_obb()
    try:
        out = obb.equity.fundamental.filings(
            symbol=symbol.upper(),
            provider="sec",
            limit=limit,
        )
        return _to_records(out)
    except Exception as exc:
        logger.debug("OpenBB SEC filings %s: %s", symbol, exc)
        return []


def get_insider_trades(symbol: str, limit: int = 20) -> list[dict[str, Any]]:
    obb = _get_obb()
    try:
        out = obb.equity.ownership.insider_trading(
            symbol=symbol.upper(),
            provider="sec",
            limit=limit,
        )
        return _to_records(out)
    except Exception as exc:
        logger.debug("OpenBB insider %s: %s", symbol, exc)
        return []


def _insider_sell_ratio(trades: list[dict[str, Any]]) -> float | None:
    sells = 0.0
    buys = 0.0
    for t in trades:
        text = " ".join(
            str(t.get(k, ""))
            for k in ("transaction", "transaction_type", "acquisition_or_disposition", "type")
        ).lower()
        shares = _to_float(_pick(t, "securities_transacted", "shares", "transaction_shares", "value")) or 0.0
        if not shares:
            continue
        if any(w in text for w in ("sale", "sell", "disposition", "s-")):
            sells += abs(shares)
        elif any(w in text for w in ("purchase", "buy", "acquisition", "p-")):
            buys += abs(shares)
    total = sells + buys
    if total <= 0:
        return None
    return sells / total


def _snap_to_dict(snap: OpenBBRiskSnapshot) -> dict[str, Any]:
    def _json_safe(value: Any) -> Any:
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        if isinstance(value, dict):
            return {k: _json_safe(v) for k, v in value.items()}
        if isinstance(value, list):
            return [_json_safe(v) for v in value]
        return value

    return {
        "governance_score": snap.governance_score,
        "warnings": snap.warnings,
        "flags": snap.flags,
        "recent_filings": _json_safe(snap.recent_filings),
        "insider_sell_ratio": snap.insider_sell_ratio,
    }


def _snap_from_dict(data: dict[str, Any]) -> OpenBBRiskSnapshot:
    return OpenBBRiskSnapshot(
        governance_score=float(data.get("governance_score", 70)),
        warnings=list(data.get("warnings") or []),
        flags=list(data.get("flags") or []),
        recent_filings=list(data.get("recent_filings") or []),
        insider_sell_ratio=data.get("insider_sell_ratio"),
    )


def get_risk_snapshot(
    symbol: str,
    *,
    allow_fetch: bool = True,
    use_cache: bool = True,
) -> OpenBBRiskSnapshot:
    """Cached SEC/insider risk. Set allow_fetch=False during bulk scans for speed."""
    sym = symbol.upper()
    if use_cache:
        from data.cache import Cache

        cached = Cache().get(f"openbb:risk:{sym}")
        if cached:
            return _snap_from_dict(cached)

    if not allow_fetch or not is_available():
        return OpenBBRiskSnapshot()

    snap = _compute_risk_snapshot_uncached(sym)
    if use_cache:
        from data.cache import Cache

        Cache().set(f"openbb:risk:{sym}", _snap_to_dict(snap), ttl_seconds=OPENBB_RISK_CACHE_TTL)
    return snap


def compute_risk_snapshot(symbol: str) -> OpenBBRiskSnapshot:
    """Backward-compatible alias — always allows fetch."""
    return get_risk_snapshot(symbol, allow_fetch=True, use_cache=True)


def _compute_risk_snapshot_uncached(symbol: str) -> OpenBBRiskSnapshot:
    snap = OpenBBRiskSnapshot()
    sym = symbol.upper()
    filings = get_sec_filings(sym, limit=5)
    snap.recent_filings = filings

    score = 72.0
    for f in filings[:5]:
        form = str(f.get("form") or f.get("form_type") or f.get("report_type") or "").upper()
        filed = f.get("filing_date") or f.get("accepted_date") or ""
        if any(form.startswith(x) for x in _RISK_FORMS):
            if form.startswith("8-K"):
                score -= 8
                snap.warnings.append(f"Recent 8-K filing ({filed}) — review material events")
                snap.flags.append("sec_8k")
            elif form.startswith(("S-1", "S-3", "424")):
                score -= 15
                snap.warnings.append(f"Recent {form} ({filed}) — possible dilution / offering")
                snap.flags.append("sec_offering")
            elif form.startswith("10-K"):
                snap.flags.append("sec_10k")

    if OPENBB_INSIDER_ON_RISK:
        insiders = get_insider_trades(sym, limit=12)
        ratio = _insider_sell_ratio(insiders)
        snap.insider_sell_ratio = ratio
        if ratio is not None:
            if ratio >= 0.75:
                score -= 12
                snap.warnings.append("Heavy insider selling in recent SEC filings")
                snap.flags.append("insider_sell")
            elif ratio >= 0.55:
                score -= 6
                snap.flags.append("insider_mixed")

    snap.governance_score = max(0.0, min(100.0, score))
    return snap


def get_equity_historical(symbol: str, period: str = "1y") -> list[dict[str, Any]]:
    obb = _get_obb()
    out = obb.equity.price.historical(
        symbol=symbol.upper(),
        provider="fmp",
        interval="1d",
        period=period,
    )
    rows = _to_records(out)
    normalized: list[dict[str, Any]] = []
    for row in rows:
        date_val = row.get("date") or row.get("datetime")
        if date_val is None:
            continue
        normalized.append(
            {
                "date": str(date_val)[:10],
                "open": float(row.get("open", 0)),
                "high": float(row.get("high", 0)),
                "low": float(row.get("low", 0)),
                "close": float(row.get("close", 0)),
                "volume": float(row.get("volume", 0)),
            }
        )
    return normalized
