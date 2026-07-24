"""DB-first price history using external provider fallback."""
from __future__ import annotations

import logging
from datetime import date
from typing import Any

import pandas as pd

from data.historical_store import HistoricalStore
from data.history_freshness import assess_history_freshness, merge_history_frames
from data.market_data_client import MarketDataClient
from utils.datetime_util import utc_iso_z, utc_now

logger = logging.getLogger(__name__)

# Minimum trading days required per period (approx)
PERIOD_MIN_BARS: dict[str, int] = {
    "5d": 3,
    "1mo": 15,
    "3mo": 50,
    "6mo": 100,
    "1y": 200,
    "2y": 400,
    "3y": 600,
    "5y": 1000,
}

PERIOD_LIMIT: dict[str, int] = {
    "5d": 10,
    "1mo": 30,
    "3mo": 80,
    "6mo": 160,
    "1y": 280,
    "2y": 560,
    "3y": 800,
    "5y": 1400,
}


def _rows_to_dataframe(rows: list[dict]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    return df[["date", "open", "high", "low", "close", "volume"]].dropna()


def avg_volume_from_history(df: pd.DataFrame | None, lookback: int = 20) -> float:
    if df is None or df.empty:
        return 0.0
    tail = df["volume"].tail(min(lookback, len(df)))
    return float(tail.mean()) if len(tail) else 0.0


def avg_dollar_volume_from_history(df: pd.DataFrame | None, lookback: int = 20) -> float:
    """Average daily dollar volume (close × volume) over lookback window."""
    if df is None or df.empty:
        return 0.0
    tail = df.tail(min(lookback, len(df)))
    if tail.empty:
        return 0.0
    return float((tail["close"] * tail["volume"]).mean())


class PriceService:
    """Local DB -> provider fallback, always persisting fresh fetches."""

    def __init__(
        self,
        store: HistoricalStore | None = None,
        market: MarketDataClient | None = None,
    ):
        self.store = store or HistoricalStore()
        self.market = market or MarketDataClient()
        self.history_fetch_count = 0
        self.last_batch_meta: dict[str, Any] | None = None

    def get_history(
        self,
        symbol: str,
        period: str = "1y",
        *,
        force_refresh: bool = False,
    ) -> pd.DataFrame:
        df, _meta = self.get_history_with_meta(symbol, period=period, force_refresh=force_refresh)
        return df

    def get_history_with_meta(
        self,
        symbol: str,
        period: str = "1y",
        *,
        force_refresh: bool = False,
    ) -> tuple[pd.DataFrame, dict[str, Any]]:
        self.history_fetch_count += 1
        sym = symbol.upper()
        min_bars = PERIOD_MIN_BARS.get(period, 200)
        limit = PERIOD_LIMIT.get(period, 500)

        rows = self.store.get_quotes(sym, limit=limit)
        local_df = _rows_to_dataframe(rows)
        local_info = assess_history_freshness(local_df, min_bars, source="local")

        use_local = (
            not force_refresh
            and local_info.is_sufficient
            and local_info.is_fresh
        )
        if use_local:
            trimmed = self._trim_period(local_df, period)
            meta = local_info.to_metadata()
            meta["price_history_refreshed_at"] = None
            return trimmed, meta

        provider_df = self.market.get_history(
            sym,
            period=period,
            skip_cache=force_refresh,
        )
        refreshed_at = utc_iso_z(utc_now()) if not provider_df.empty else None

        if provider_df.empty:
            if not local_df.empty:
                trimmed = self._trim_period(local_df, period)
                stale_meta = assess_history_freshness(trimmed, min_bars, source="local_stale")
                meta = stale_meta.to_metadata()
                meta["price_history_refreshed_at"] = None
                meta["price_history_is_stale"] = True
                return trimmed, meta
            empty_meta = assess_history_freshness(local_df, min_bars, source="none").to_metadata()
            empty_meta["price_history_refreshed_at"] = None
            return local_df, empty_meta

        merged = merge_history_frames(local_df, provider_df)
        self._persist(sym, merged)
        trimmed = self._trim_period(merged, period)
        merged_info = assess_history_freshness(trimmed, min_bars, source="provider")
        meta = merged_info.to_metadata()
        meta["price_history_refreshed_at"] = refreshed_at
        return trimmed, meta

    def get_spy_history(self, period: str = "1y", *, force_refresh: bool = False) -> pd.DataFrame:
        return self.get_history("SPY", period=period, force_refresh=force_refresh)

    def get_info(self, symbol: str) -> dict[str, Any]:
        return self.market.get_info(symbol.upper())

    def download_batch(
        self,
        symbols: list[str],
        period: str = "6mo",
        chunk_size: int = 50,
        *,
        max_runtime_seconds: int = 45,
        min_bars: int | None = None,
        bar_limit: int | None = None,
        max_session_lag: int | None = None,
    ) -> dict[str, pd.DataFrame]:
        """Load from DB where sufficient; fetch only missing symbols."""
        from config import SCAN_BULK_COVERAGE_MIN

        unique = list(dict.fromkeys(s.upper() for s in symbols if s))
        sufficiency_bars = min_bars if min_bars is not None else PERIOD_MIN_BARS.get(period, 100)
        trim_limit = bar_limit if bar_limit is not None else PERIOD_LIMIT.get(period, 500)
        result: dict[str, pd.DataFrame] = {}
        missing: list[str] = []
        database_hits = 0
        lag_0 = 0
        lag_1 = 0
        stale_symbols = 0

        for sym in unique:
            rows = self.store.get_quotes(sym, limit=trim_limit)
            df = _rows_to_dataframe(rows)
            info = assess_history_freshness(
                df,
                sufficiency_bars,
                max_session_lag=max_session_lag,
            )
            if info.is_sufficient and info.is_fresh:
                result[sym] = self._trim_period(df, period, bar_limit=trim_limit)
                database_hits += 1
                if info.session_lag <= 0:
                    lag_0 += 1
                elif info.session_lag == 1:
                    lag_1 += 1
            else:
                missing.append(sym)
                if info.session_lag > (max_session_lag if max_session_lag is not None else 1):
                    stale_symbols += 1

        source = "db"
        provider_requested = len(missing)
        provider_received = 0
        if missing:
            logger.info(
                "PriceService: fetching %s/%s symbols from provider fallback (%s)",
                len(missing),
                len(unique),
                period,
            )
            fetched = self.market.download_batch(
                missing,
                period=period,
                chunk_size=chunk_size,
                use_alpha_vantage_fallback=False,
                max_runtime_seconds=max_runtime_seconds,
                alpha_vantage_probe_symbols=5,
            )
            market_meta = getattr(self.market, "last_batch_meta", None) or {}
            source = str(market_meta.get("source") or "provider")
            if result:
                source = f"db+{source}"
            for sym, df in fetched.items():
                if not df.empty:
                    trimmed = self._trim_period(df, period, bar_limit=trim_limit)
                    self._persist(sym, trimmed)
                    result[sym.upper()] = trimmed
                    provider_received += 1

        requested = len(unique)
        received = len(result)
        coverage = (received / requested) if requested else 1.0
        live_refresh_coverage = (
            (provider_received / provider_requested) if provider_requested else 1.0
        )
        self.last_batch_meta = {
            "requested": requested,
            "received": received,
            "missing_count": max(0, requested - received),
            "coverage": round(coverage, 4),
            "source": source,
            "partial": bool(requested and coverage < SCAN_BULK_COVERAGE_MIN),
            "database_hits": database_hits,
            "provider_requested": provider_requested,
            "provider_received": provider_received,
            "availability_coverage": round(coverage, 4),
            "live_refresh_coverage": round(live_refresh_coverage, 4),
            "lag_0_symbols": lag_0,
            "lag_1_symbols": lag_1,
            "stale_symbols": stale_symbols,
            "min_bars": sufficiency_bars,
            "bar_limit": trim_limit,
        }
        return result

    def _persist(self, symbol: str, df: pd.DataFrame) -> None:
        rows = [
            {
                "date": r["date"].isoformat() if hasattr(r["date"], "isoformat") else str(r["date"])[:10],
                "open": float(r["open"]),
                "high": float(r["high"]),
                "low": float(r["low"]),
                "close": float(r["close"]),
                "volume": float(r["volume"]),
            }
            for _, r in df.iterrows()
        ]
        try:
            self.store.upsert_quotes(symbol, rows)
        except Exception as exc:
            logger.warning("Failed to persist quotes for %s: %s", symbol, exc)

    @staticmethod
    def _trim_period(
        df: pd.DataFrame,
        period: str,
        *,
        bar_limit: int | None = None,
    ) -> pd.DataFrame:
        bars = bar_limit if bar_limit is not None else PERIOD_LIMIT.get(period)
        if bars and len(df) > bars:
            return df.iloc[-bars:].copy().reset_index(drop=True)
        return df.copy().reset_index(drop=True)

    def quote_from_history(self, symbol: str, hist: pd.DataFrame | None = None) -> dict[str, Any]:
        if hist is None or hist.empty:
            hist = self.get_history(symbol, period="1mo")
        if hist.empty:
            return {}
        price = float(hist["close"].iloc[-1])
        avg_vol = avg_volume_from_history(hist)
        return {
            "symbol": symbol.upper(),
            "currentPrice": price,
            "averageVolume": avg_vol,
        }

    def _live_quote_price(self, symbol: str) -> tuple[float | None, dict[str, Any]]:
        quote = self.market.get_quote(symbol.upper())
        price = quote.get("currentPrice") or quote.get("price")
        if price is None:
            return None, quote
        return float(price), quote

    @staticmethod
    def _session_date_et() -> date:
        from services.data_freshness_service import NY_TZ

        return utc_now().astimezone(NY_TZ).date()

    def _upsert_live_quote_bar(self, symbol: str, quote: dict[str, Any], price: float) -> None:
        """Persist today's session bar from a live quote so holdings refresh updates DB."""
        sym = symbol.upper()
        session_date = self._session_date_et()
        row = {
            "date": pd.Timestamp(session_date),
            "open": float(quote.get("open") or price),
            "high": float(quote.get("high") or price),
            "low": float(quote.get("low") or price),
            "close": float(price),
            "volume": float(quote.get("volume") or 0),
        }
        local_rows = self.store.get_quotes(sym, limit=PERIOD_LIMIT.get("5d", 10))
        local_df = _rows_to_dataframe(local_rows)
        merged = merge_history_frames(local_df, pd.DataFrame([row]))
        self._persist(sym, merged)

    def get_latest_price(self, symbol: str, *, force_refresh: bool = False) -> float | None:
        """Latest mark for portfolio — live quote during market hours, else last daily close."""
        sym = symbol.upper()
        from services.data_freshness_service import get_market_session_band

        band = get_market_session_band()
        use_live = force_refresh or band in ("regular", "extended")
        if use_live:
            price, _quote = self._live_quote_price(sym)
            if price is not None and price > 0:
                return price

        df = self.get_history(sym, period="5d", force_refresh=force_refresh)
        if df is None or df.empty:
            return None
        return float(df["close"].iloc[-1])

    def refresh_latest_price(self, symbol: str, *, force: bool = False) -> float | None:
        """Fetch live quote + daily history for a holding symbol."""
        sym = symbol.upper()
        price, quote = self._live_quote_price(sym)
        if price is not None and price > 0:
            try:
                self._upsert_live_quote_bar(sym, quote, price)
            except Exception as exc:
                logger.warning("Failed to persist live quote bar for %s: %s", sym, exc)

        self.get_history(sym, period="5d", force_refresh=force)

        if price is not None and price > 0:
            return price

        df = self.get_history(sym, period="5d")
        if df is None or df.empty:
            return None
        return float(df["close"].iloc[-1])
