"""AkShare client for US quote/history without paid quotas."""
from __future__ import annotations

import logging
import time
from datetime import date, timedelta
from typing import Any

import pandas as pd

from config import AKSHARE_ENABLED
from data.cache import Cache

logger = logging.getLogger(__name__)


class AkShareClient:
    _SPOT_CACHE_TTL = 45
    _SYMBOL_MAP_TTL = 86400
    _SYMBOL_MAP_FAIL_TTL = 120
    _SYMBOL_FAIL_TTL = 300
    _GLOBAL_FAIL_TTL = 1800

    def __init__(self, cache: Cache | None = None):
        self.cache = cache or Cache()
        self.enabled = AKSHARE_ENABLED
        self._ak = None

    def _get_ak(self):
        if not self.enabled:
            return None
        if self._is_globally_blocked():
            return None
        if self._ak is not None:
            return self._ak
        try:
            import akshare as ak

            self._ak = ak
            return ak
        except Exception as exc:
            logger.warning("AkShare import failed: %s", exc)
            return None

    def _global_fail_key(self) -> str:
        return "akshare:disabled:global_fail"

    def _is_globally_blocked(self) -> bool:
        return bool(self.cache.get(self._global_fail_key()))

    def _mark_globally_blocked(self, reason: str) -> None:
        self.cache.set(
            self._global_fail_key(),
            {"blocked": True, "reason": reason, "at": time.time()},
            self._GLOBAL_FAIL_TTL,
        )

    def _should_disable_globally(self, exc: Exception) -> bool:
        msg = str(exc)
        return any(
            token in msg
            for token in (
                "Tunnel connection failed: 403",
                "ProxyError",
                "NameResolutionError",
                "Max retries exceeded with url",
            )
        )

    def _sanitize_symbol(self, symbol: str) -> str:
        return symbol.upper().replace("/", "-").strip()

    def _symbol_fail_key(self, symbol: str) -> str:
        return f"akshare:us:hist:fail:{self._sanitize_symbol(symbol)}"

    def _is_symbol_temporarily_blocked(self, symbol: str) -> bool:
        return bool(self.cache.get(self._symbol_fail_key(symbol)))

    def _mark_symbol_failed(self, symbol: str) -> None:
        self.cache.set(
            self._symbol_fail_key(symbol),
            {"failed": True, "at": time.time()},
            self._SYMBOL_FAIL_TTL,
        )

    def _clear_symbol_failure(self, symbol: str) -> None:
        # Cache helper does not support delete; overwrite with tiny TTL.
        self.cache.set(self._symbol_fail_key(symbol), {"failed": False}, 0.01)

    def _get_spot_frame(self) -> pd.DataFrame:
        cached = self.cache.get("akshare:us:spot")
        if cached and isinstance(cached, dict):
            rows = cached.get("rows")
            if isinstance(rows, list):
                df = pd.DataFrame(rows)
                if not df.empty:
                    return df

        ak = self._get_ak()
        if not ak:
            return pd.DataFrame()
        df = ak.stock_us_spot_em()
        if df is None or df.empty:
            return pd.DataFrame()
        self.cache.set("akshare:us:spot", {"rows": df.to_dict(orient="records")}, self._SPOT_CACHE_TTL)
        return df

    def _symbol_map(self) -> dict[str, str]:
        cached = self.cache.get("akshare:us:symbol_map")
        if cached:
            return cached
        if self.cache.get("akshare:us:symbol_map:fetch_failed"):
            return {}
        try:
            df = self._get_spot_frame()
            mapping: dict[str, str] = {}
            if df is not None and not df.empty and "代码" in df.columns:
                for _, row in df.iterrows():
                    code = str(row.get("代码") or "").strip().upper()
                    if not code:
                        continue
                    ticker = code.split(".")[-1].upper()
                    mapping[ticker] = code
            self.cache.set("akshare:us:symbol_map", mapping, self._SYMBOL_MAP_TTL)
            return mapping
        except Exception as exc:
            logger.warning("AkShare symbol map fetch failed: %s", exc)
            self.cache.set("akshare:us:symbol_map:fetch_failed", {"failed": True}, self._SYMBOL_MAP_FAIL_TTL)
            return {}

    def _candidate_ak_symbols(self, symbol: str) -> list[str]:
        sym = self._sanitize_symbol(symbol)
        mapping = self._symbol_map()

        candidates: list[str] = []
        mapped = mapping.get(sym)
        if mapped:
            candidates.append(mapped)

        alt = sym.replace("-", ".")
        if alt != sym and alt in mapping:
            candidates.append(mapping[alt])

        if "-" in sym:
            prefix, suffix = sym.split("-", 1)
            if prefix and suffix:
                candidates.append(f"105.{prefix}.{suffix}")

        candidates.extend([f"105.{sym}", sym])
        if alt != sym:
            candidates.append(f"105.{alt}")

        seen: set[str] = set()
        out: list[str] = []
        for c in candidates:
            key = c.upper().strip()
            if key and key not in seen:
                seen.add(key)
                out.append(key)
        return out

    def get_quote(self, symbol: str) -> dict[str, Any]:
        sym = self._sanitize_symbol(symbol)
        try:
            df = self._get_spot_frame()
            if df is None or df.empty or "代码" not in df.columns:
                return {}

            codes = [c.upper() for c in self._candidate_ak_symbols(sym)]
            row_df = df[df["代码"].astype(str).str.upper().isin(codes)]
            if row_df.empty:
                row_df = df[df["代码"].astype(str).str.upper().str.endswith(f".{sym}")]
            if row_df.empty and "-" in sym:
                row_df = df[df["代码"].astype(str).str.upper().str.endswith(f".{sym.replace('-', '.')}")]
            if row_df.empty:
                return {}

            row = row_df.iloc[0]
            price = _to_float(row.get("最新价"))
            if price is None:
                return {}
            return {
                "symbol": sym,
                "currentPrice": price,
                "price": price,
                "marketCap": _to_float(row.get("总市值")),
                "averageVolume": _to_float(row.get("成交量")),
                "trailingPE": _to_float(row.get("市盈率")),
                "source": "akshare",
            }
        except Exception as exc:
            if self._should_disable_globally(exc):
                self._mark_globally_blocked(f"quote:{exc}")
            logger.warning("AkShare quote failed for %s: %s", sym, exc)
            return {}

    def get_history(self, symbol: str, period_days: int = 365) -> pd.DataFrame:
        ak = self._get_ak()
        if not ak:
            return pd.DataFrame()

        sym = self._sanitize_symbol(symbol)
        if self._is_symbol_temporarily_blocked(sym):
            return pd.DataFrame()

        end = date.today()
        start = end - timedelta(days=max(30, period_days * 2))
        codes = self._candidate_ak_symbols(sym)

        for code in codes:
            for attempt in range(2):
                try:
                    df = ak.stock_us_hist(
                        symbol=code,
                        period="daily",
                        start_date=start.strftime("%Y%m%d"),
                        end_date=end.strftime("%Y%m%d"),
                        adjust="",
                    )
                    out = _normalize_history_frame(df, period_days=period_days)
                    if not out.empty:
                        self._clear_symbol_failure(sym)
                        return out
                except Exception as exc:
                    if self._should_disable_globally(exc):
                        self._mark_globally_blocked(f"history:{exc}")
                        logger.warning("AkShare temporarily disabled after network/proxy failures")
                        return pd.DataFrame()
                    if attempt == 0:
                        # one quick retry for transient remote disconnects
                        time.sleep(0.2)
                        continue
                    logger.warning("AkShare history failed for %s (%s): %s", sym, code, exc)

        self._mark_symbol_failed(sym)
        return pd.DataFrame()


def _normalize_history_frame(df: pd.DataFrame | None, *, period_days: int) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()

    rename = {
        "日期": "date",
        "开盘": "open",
        "收盘": "close",
        "最高": "high",
        "最低": "low",
        "成交量": "volume",
    }
    for src, dst in rename.items():
        if src in df.columns:
            df = df.rename(columns={src: dst})

    needed = ["date", "open", "high", "low", "close", "volume"]
    if not all(c in df.columns for c in needed):
        return pd.DataFrame()

    out = df[needed].copy()
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    for c in ("open", "high", "low", "close", "volume"):
        out[c] = pd.to_numeric(out[c], errors="coerce")
    out = out.dropna().sort_values("date").reset_index(drop=True)
    if out.empty:
        return out
    if len(out) > period_days:
        out = out.tail(period_days).reset_index(drop=True)
    return out


def _to_float(val: Any) -> float | None:
    try:
        if val is None:
            return None
        f = float(val)
        return f if f == f else None
    except (TypeError, ValueError):
        return None
