"""Market data client (AkShare/FMP/Finnhub/AV) for OHLC and quote data."""
from __future__ import annotations

from datetime import date, timedelta
import logging
import time
from typing import Any

import pandas as pd
import requests

from config import (
    AKSHARE_ENABLED,
    ALPHA_VANTAGE_API_KEY,
    ALPHA_VANTAGE_ENABLED,
    FINNHUB_API_KEY,
    FINNHUB_ENABLED,
    FMP_API_KEY,
    FMP_ENABLED,
    PRIMARY_FUNDAMENTALS_SOURCE,
    PRIMARY_PRICE_SOURCE,
    SCAN_BULK_COVERAGE_MIN,
)
from data.akshare_client import AkShareClient
from data.av_client import AlphaVantageClient
from data.cache import Cache
from data.finnhub_client import FinnhubClient
from data.fmp_client import FMPClient
from data import yfinance_client as yf_client

logger = logging.getLogger(__name__)


class MarketDataClient:
    _period_bars: dict[str, int] = {
        "5d": 10,
        "1mo": 30,
        "3mo": 90,
        "6mo": 180,
        "1y": 365,
        "2y": 730,
        "3y": 1095,
        "5y": 1825,
    }

    def __init__(self, cache: Cache | None = None):
        self.cache = cache or Cache()
        self._last_call = 0.0
        self._min_interval = 0.2
        self.last_batch_meta: dict[str, Any] | None = None
        self.ak = AkShareClient(cache=self.cache) if AKSHARE_ENABLED else None
        self.fmp = FMPClient(cache=self.cache) if FMP_API_KEY and FMP_ENABLED else None
        self.finnhub = FinnhubClient(cache=self.cache) if FINNHUB_API_KEY and FINNHUB_ENABLED else None
        self.av = AlphaVantageClient(cache=self.cache) if ALPHA_VANTAGE_API_KEY and ALPHA_VANTAGE_ENABLED else None

    def _period_to_days(self, period: str) -> int:
        return int(self._period_bars.get(period, 365))

    def _throttle(self) -> None:
        elapsed = time.time() - self._last_call
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_call = time.time()

    def _get_history_fmp(self, symbol: str, period: str) -> pd.DataFrame:
        if not self.fmp or not self.fmp.api_key:
            return pd.DataFrame()
        self._throttle()
        bars = self._period_bars.get(period, 365)
        try:
            data = self.fmp._get(f"/historical-price-full/{symbol}", {"timeseries": bars})
            if not isinstance(data, dict):
                return pd.DataFrame()
            rows = data.get("historical") or []
            if not isinstance(rows, list) or not rows:
                return pd.DataFrame()
            return pd.DataFrame(
                [
                    {
                        "date": r.get("date"),
                        "open": r.get("open"),
                        "high": r.get("high"),
                        "low": r.get("low"),
                        "close": r.get("close"),
                        "volume": r.get("volume"),
                    }
                    for r in rows
                    if r.get("date") is not None
                ]
            )
        except Exception as exc:
            logger.warning("FMP history fetch failed for %s: %s", symbol, exc)
            return pd.DataFrame()

    def _get_history_akshare(self, symbol: str, period: str) -> pd.DataFrame:
        if not self.ak:
            return pd.DataFrame()
        days = self._period_to_days(period)
        return self.ak.get_history(symbol, period_days=days)

    def _get_history_alpha_vantage(self, symbol: str, period: str) -> pd.DataFrame:
        if not self.av or not self.av.api_key:
            return pd.DataFrame()
        self._throttle()
        try:
            params = {
                # Free-tier endpoint; adjusted endpoint is premium-only.
                "function": "TIME_SERIES_DAILY",
                "symbol": symbol,
                # "full" is premium-only on many keys; compact keeps scans operational.
                "outputsize": "compact",
                "apikey": self.av.api_key,
            }
            response = requests.get(self.av.BASE_URL, params=params, timeout=20)
            response.raise_for_status()
            data = response.json()
            series = data.get("Time Series (Daily)")
            if not isinstance(series, dict) or not series:
                return pd.DataFrame()

            bars = self._period_bars.get(period, 365)
            min_date = date.today() - timedelta(days=max(10, int(bars * 1.7)))
            rows: list[dict[str, Any]] = []
            for dt, values in series.items():
                if dt < min_date.isoformat():
                    continue
                rows.append(
                    {
                        "date": dt,
                        "open": values.get("1. open"),
                        "high": values.get("2. high"),
                        "low": values.get("3. low"),
                        "close": values.get("4. close"),
                        "volume": values.get("5. volume"),
                    }
                )
            return pd.DataFrame(rows)
        except Exception as exc:
            logger.warning("Alpha Vantage history fetch failed for %s: %s", symbol, exc)
            return pd.DataFrame()

    def _get_history_yfinance(self, symbol: str, period: str) -> pd.DataFrame:
        return yf_client.get_history(symbol, period=period)

    def _history_providers(self) -> list:
        """Ordered OHLC providers — yfinance first when FMP is blocked or not primary."""
        providers: list = []
        if PRIMARY_PRICE_SOURCE == "akshare":
            providers.append(self._get_history_akshare)
        if PRIMARY_PRICE_SOURCE == "fmp" and self.fmp and not FMPClient.is_disabled():
            providers.append(self._get_history_fmp)
        if PRIMARY_PRICE_SOURCE not in ("akshare", "fmp"):
            providers.append(self._get_history_yfinance)
        if self._get_history_yfinance not in providers:
            providers.append(self._get_history_yfinance)
        if self.fmp and not FMPClient.is_disabled() and self._get_history_fmp not in providers:
            providers.append(self._get_history_fmp)
        if self.ak and self._get_history_akshare not in providers:
            providers.append(self._get_history_akshare)
        return providers

    def get_history(
        self,
        symbol: str,
        period: str = "1y",
        *,
        allow_alpha_vantage_fallback: bool = True,
        skip_cache: bool = False,
    ) -> pd.DataFrame:
        sym = symbol.upper()
        if not skip_cache:
            cached = self.cache.get_price_cache(sym)
            if cached and cached.get("period") == period:
                df = pd.DataFrame(cached["rows"])
                if not df.empty:
                    df["date"] = pd.to_datetime(df["date"])
                    return df

        df = pd.DataFrame()
        for provider in self._history_providers():
            df = provider(sym, period=period)
            if not df.empty:
                break
        if df.empty and allow_alpha_vantage_fallback:
            df = self._get_history_alpha_vantage(sym, period=period)
        df = _normalize_hist_frame(df)
        if df.empty:
            return df

        self.cache.set_price_cache(
            sym,
            {
                "period": period,
                "rows": [
                    {
                        "date": r["date"].isoformat(),
                        "open": float(r["open"]),
                        "high": float(r["high"]),
                        "low": float(r["low"]),
                        "close": float(r["close"]),
                        "volume": float(r["volume"]),
                    }
                    for _, r in df.iterrows()
                ],
            },
        )
        return df

    def get_quote(self, symbol: str) -> dict[str, Any]:
        sym = symbol.upper()
        if self.ak and PRIMARY_PRICE_SOURCE == "akshare":
            quote = self.ak.get_quote(sym)
            if quote:
                return quote
        if self.finnhub:
            quote = self.finnhub.get_quote(sym)
            if quote:
                return quote
        if self.ak:
            quote = self.ak.get_quote(sym)
            if quote:
                return quote
        if self.fmp:
            profile = self.fmp.get_profile(sym)
            if profile:
                price = profile.get("price")
                return {
                    "symbol": sym,
                    "currentPrice": price,
                    "price": price,
                    "marketCap": profile.get("marketCap"),
                    "sector": profile.get("sector"),
                    "industry": profile.get("industry"),
                    "beta": profile.get("beta"),
                    "source": "fmp",
                }
        yf_info = yf_client.get_info(sym)
        if yf_info.get("currentPrice") or yf_info.get("marketCap"):
            return yf_info
        return {}

    @staticmethod
    def _fill_missing(target: dict[str, Any], source: dict[str, Any], fields: list[str]) -> None:
        for field in fields:
            if not target.get(field) and source.get(field) not in (None, ""):
                target[field] = source[field]

    def get_info(self, symbol: str) -> dict[str, Any]:
        sym = symbol.upper()
        cached = self.cache.get(f"info:{sym}")
        if cached:
            return cached

        quote = self.get_quote(sym)
        profile: dict[str, Any] = {}
        ratios: dict[str, Any] = {}
        if self.fmp and (
            PRIMARY_FUNDAMENTALS_SOURCE == "fmp"
            or not quote.get("trailingPE")
            or not quote.get("marketCap")
        ):
            profile = self.fmp.get_profile(sym)
            ratios = self.fmp.get_ratios(sym)
        av = self.av.get_overview(sym) if self.av else {}

        info = {**profile, **ratios, **quote}
        if av:
            self._fill_missing(
                info,
                {
                    "shortName": av.get("name"),
                    "sector": av.get("sector"),
                    "industry": av.get("industry"),
                    "marketCap": av.get("market_cap"),
                    "beta": av.get("beta"),
                    "trailingPE": av.get("pe_ratio"),
                    "profitMargins": av.get("profit_margin"),
                    "fiftyTwoWeekHigh": av.get("52_week_high"),
                    "fiftyTwoWeekLow": av.get("52_week_low"),
                },
                [
                    "shortName",
                    "sector",
                    "industry",
                    "marketCap",
                    "beta",
                    "trailingPE",
                    "profitMargins",
                    "fiftyTwoWeekHigh",
                    "fiftyTwoWeekLow",
                ],
            )

        # Final bounded Yahoo fundamentals fallback when paid providers are sparse.
        if not info.get("currentPrice") or not info.get("marketCap") or not info.get("sector"):
            yf_info = yf_client.get_info(sym)
            if yf_info:
                self._fill_missing(
                    info,
                    yf_info,
                    [
                        "shortName",
                        "sector",
                        "industry",
                        "marketCap",
                        "currentPrice",
                        "averageVolume",
                        "beta",
                        "trailingPE",
                        "profitMargins",
                        "revenueGrowth",
                        "earningsGrowth",
                        "debtToEquity",
                        "returnOnEquity",
                        "freeCashflow",
                        "totalRevenue",
                        "fiftyTwoWeekHigh",
                        "fiftyTwoWeekLow",
                    ],
                )
                if not info.get("source"):
                    info["source"] = yf_info.get("source") or "yfinance"

        slim = {
            "symbol": sym,
            "shortName": info.get("shortName") or info.get("name") or "",
            "sector": info.get("sector", ""),
            "industry": info.get("industry", ""),
            "marketCap": info.get("marketCap"),
            "currentPrice": info.get("currentPrice") or info.get("price"),
            "averageVolume": info.get("averageVolume"),
            "beta": info.get("beta"),
            "trailingPE": info.get("trailingPE"),
            "profitMargins": info.get("profitMargins"),
            "revenueGrowth": info.get("revenueGrowth"),
            "earningsGrowth": info.get("earningsGrowth"),
            "debtToEquity": info.get("debtToEquity"),
            "returnOnEquity": info.get("returnOnEquity"),
            "freeCashflow": info.get("freeCashflow"),
            "totalRevenue": info.get("totalRevenue"),
            "ebitdaMargins": info.get("ebitdaMargins"),
            "fiftyTwoWeekHigh": info.get("fiftyTwoWeekHigh"),
            "fiftyTwoWeekLow": info.get("fiftyTwoWeekLow"),
            "source": info.get("source"),
        }
        ttl = self._info_cache_ttl(slim)
        self.cache.set(f"info:{sym}", slim, ttl)
        return slim

    @staticmethod
    def _info_cache_ttl(slim: dict[str, Any]) -> int:
        """Completeness-aware TTL — incomplete records must not stick for 24h."""
        price = slim.get("currentPrice")
        mcap = slim.get("marketCap")
        has_price = price not in (None, "", 0)
        has_mcap = mcap not in (None, "", 0)
        if not has_price and not has_mcap:
            return 300
        if has_price ^ has_mcap:
            return 900
        sector = slim.get("sector") or ""
        rich = bool(sector) and bool(
            slim.get("trailingPE")
            or slim.get("revenueGrowth")
            or slim.get("earningsGrowth")
            or slim.get("profitMargins")
        )
        if rich:
            return 86400
        return 3600

    def bulk_info(self, symbols: list[str]) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        for symbol in symbols:
            try:
                result[symbol.upper()] = self.get_info(symbol)
            except Exception as exc:
                logger.warning("Failed info for %s: %s", symbol, exc)
        return result

    def get_spy_history(self, period: str = "1y") -> pd.DataFrame:
        return self.get_history("SPY", period=period)

    def _fill_missing_via_fmp(
        self,
        result: dict[str, pd.DataFrame],
        missing: list[str],
        period: str,
        *,
        deadline: float | None,
    ) -> list[str]:
        """Bounded FMP fill for symbols Yahoo bulk missed — no Yahoo/AkShare hammering."""
        if not missing or not self.fmp or FMPClient.is_disabled():
            return missing
        remaining = list(missing)
        filled = 0
        for sym in list(remaining):
            if deadline is not None and time.monotonic() >= deadline:
                logger.warning(
                    "Batch history: FMP fill hit deadline after %s fills (%s still missing)",
                    filled,
                    len([s for s in remaining if s not in result]),
                )
                break
            try:
                df = self._get_history_fmp(sym, period=period)
                df = _normalize_hist_frame(df)
                if not df.empty:
                    result[sym] = df
                    filled += 1
            except Exception as exc:
                logger.warning("FMP bulk fill failed for %s: %s", sym, exc)
        if filled:
            logger.info(
                "Batch history: FMP fill recovered %s/%s missing symbols",
                filled,
                len(missing),
            )
        return [s for s in missing if s not in result]

    def _set_batch_meta(
        self,
        *,
        requested: int,
        result: dict[str, pd.DataFrame],
        source: str,
    ) -> None:
        received = len(result)
        coverage = (received / requested) if requested else 1.0
        self.last_batch_meta = {
            "requested": requested,
            "received": received,
            "missing_count": max(0, requested - received),
            "coverage": round(coverage, 4),
            "source": source,
            "partial": bool(requested and coverage < SCAN_BULK_COVERAGE_MIN),
        }

    def download_batch(
        self,
        symbols: list[str],
        period: str = "6mo",
        chunk_size: int = 50,
        *,
        use_alpha_vantage_fallback: bool = False,
        max_runtime_seconds: int = 45,
        alpha_vantage_probe_symbols: int = 5,
    ) -> dict[str, pd.DataFrame]:
        result: dict[str, pd.DataFrame] = {}
        unique = list(dict.fromkeys(s.upper() for s in symbols if s))
        if not unique:
            self._set_batch_meta(requested=0, result=result, source="none")
            return result

        deadline: float | None = None
        if max_runtime_seconds and max_runtime_seconds > 0:
            deadline = time.monotonic() + float(max_runtime_seconds)
        missing = list(unique)
        source = "none"

        def _remaining() -> float | None:
            if deadline is None:
                return None
            return max(0.0, deadline - time.monotonic())

        # Fast path: bulk yfinance when FMP is blocked or not the primary price source.
        use_yf_bulk = PRIMARY_PRICE_SOURCE != "fmp" or FMPClient.is_disabled()
        if use_yf_bulk and missing:
            rem = _remaining()
            yf_batch = yf_client.download_batch(
                missing,
                period=period,
                max_runtime_seconds=rem if rem is not None else None,
            )
            for sym, df in yf_batch.items():
                if not df.empty:
                    result[sym] = df
            missing = [s for s in missing if s not in result]
            yf_count = len(result)
            source = "yfinance"
            coverage = yf_count / len(unique) if unique else 1.0
            logger.info(
                "Batch history: yfinance returned %s/%s symbols (coverage=%.1f%%, %s)",
                yf_count,
                len(unique),
                coverage * 100.0,
                period,
            )
            # One bounded FMP fill when coverage is below the publish gate — still no
            # per-symbol Yahoo/AkShare hammering after the bulk pass.
            if missing and coverage < SCAN_BULK_COVERAGE_MIN:
                missing = self._fill_missing_via_fmp(
                    result,
                    missing,
                    period,
                    deadline=deadline,
                )
                if len(result) > yf_count:
                    source = "yfinance+fmp" if yf_count else "fmp"
            if missing:
                logger.warning(
                    "Batch history: skipping per-symbol fallback for %s symbols after bulk path",
                    len(missing),
                )
            self._set_batch_meta(requested=len(unique), result=result, source=source)
            return result

        batch_size = max(1, chunk_size)
        source = "per_symbol"
        for i in range(0, len(missing), batch_size):
            if deadline is not None and time.monotonic() >= deadline:
                logger.warning(
                    "Batch history fetch reached runtime deadline; returning partial results (%s/%s symbols)",
                    len(result),
                    len(unique),
                )
                break
            chunk = missing[i : i + batch_size]
            for sym in chunk:
                if deadline is not None and time.monotonic() >= deadline:
                    logger.warning(
                        "Batch history fetch reached runtime deadline mid-chunk; returning partial (%s/%s)",
                        len(result),
                        len(unique),
                    )
                    self._set_batch_meta(requested=len(unique), result=result, source=source)
                    return result
                try:
                    df = self.get_history(
                        sym,
                        period=period,
                        allow_alpha_vantage_fallback=use_alpha_vantage_fallback,
                    )
                    if not df.empty:
                        result[sym] = df
                except Exception as exc:
                    logger.warning("Batch history failed for %s: %s", sym, exc)
            time.sleep(0.05)

        # If all providers failed, probe a few symbols via Alpha Vantage.
        if not result and not use_alpha_vantage_fallback and self.av and alpha_vantage_probe_symbols > 0:
            probes = unique[:alpha_vantage_probe_symbols]
            logger.info(
                "Batch history fallback: probing %s symbols via Alpha Vantage",
                len(probes),
            )
            source = "alpha_vantage_probe"
            for sym in probes:
                if deadline is not None and time.monotonic() >= deadline:
                    break
                try:
                    df = self.get_history(
                        sym,
                        period=period,
                        allow_alpha_vantage_fallback=True,
                    )
                    if not df.empty:
                        result[sym] = df
                except Exception as exc:
                    logger.warning("AV probe history failed for %s: %s", sym, exc)
        self._set_batch_meta(requested=len(unique), result=result, source=source)
        return result

    def get_latest_quote_from_history(self, symbol: str, hist: pd.DataFrame | None = None) -> dict:
        if hist is None or hist.empty:
            hist = self.get_history(symbol, period="5d")
        if hist.empty:
            return {}
        row = hist.iloc[-1]
        avg_vol = float(hist["volume"].tail(20).mean()) if len(hist) >= 5 else float(row["volume"])
        return {
            "symbol": symbol.upper(),
            "currentPrice": float(row["close"]),
            "averageVolume": avg_vol,
        }


def _normalize_hist_frame(hist: pd.DataFrame) -> pd.DataFrame:
    if hist.empty:
        return pd.DataFrame()
    if "date" in hist.columns:
        df = hist.copy()
    else:
        df = hist.reset_index()
    date_col = "date" if "date" in df.columns else ("Date" if "Date" in df.columns else df.columns[0])
    rename = {
        date_col: "date",
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Volume": "volume",
    }
    cols = {k: v for k, v in rename.items() if k in df.columns}
    df = df.rename(columns=cols)
    if "date" not in df.columns:
        return pd.DataFrame()
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
    needed = ["date", "open", "high", "low", "close", "volume"]
    for c in needed:
        if c not in df.columns:
            return pd.DataFrame()
    for c in ("open", "high", "low", "close", "volume"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df[needed].dropna().sort_values("date").reset_index(drop=True)

