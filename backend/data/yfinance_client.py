"""Yahoo Finance fallback for US equity OHLC when paid APIs are blocked or slow."""
from __future__ import annotations

import logging
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

_PERIOD_TO_YF: dict[str, str] = {
    "5d": "5d",
    "1mo": "1mo",
    "3mo": "3mo",
    "6mo": "6mo",
    "1y": "1y",
    "2y": "2y",
    "3y": "3y",
    "5y": "5y",
}


def _import_yfinance():
    try:
        import yfinance as yf

        return yf
    except ImportError:
        logger.debug("yfinance not installed — OHLC fallback unavailable")
        return None


def get_history(symbol: str, period: str = "1y") -> pd.DataFrame:
    yf = _import_yfinance()
    if yf is None:
        return pd.DataFrame()
    sym = symbol.upper()
    yf_period = _PERIOD_TO_YF.get(period, period)
    try:
        hist = yf.Ticker(sym).history(period=yf_period, auto_adjust=True)
        return _normalize(hist)
    except Exception as exc:
        logger.warning("yfinance history failed for %s: %s", sym, exc)
        return pd.DataFrame()


def download_batch(symbols: list[str], period: str = "6mo") -> dict[str, pd.DataFrame]:
    """Batch OHLC via yfinance.download — much faster than per-symbol API calls."""
    yf = _import_yfinance()
    if yf is None or not symbols:
        return {}
    unique = list(dict.fromkeys(s.upper() for s in symbols if s))
    yf_period = _PERIOD_TO_YF.get(period, period)
    result: dict[str, pd.DataFrame] = {}
    chunk_size = 40
    for i in range(0, len(unique), chunk_size):
        chunk = unique[i : i + chunk_size]
        tickers = " ".join(chunk)
        try:
            raw = yf.download(
                tickers,
                period=yf_period,
                group_by="ticker",
                auto_adjust=True,
                threads=True,
                progress=False,
            )
        except Exception as exc:
            logger.warning("yfinance batch download failed: %s", exc)
            continue
        if raw is None or raw.empty:
            continue
        if len(chunk) == 1:
            sym = chunk[0]
            df = _normalize(raw)
            if not df.empty:
                result[sym] = df
            continue
        for sym in chunk:
            try:
                if sym not in raw.columns.get_level_values(0):
                    continue
                df = _normalize(raw[sym])
                if not df.empty:
                    result[sym] = df
            except Exception as exc:
                logger.debug("yfinance batch parse failed for %s: %s", sym, exc)
    return result


def get_info(symbol: str) -> dict[str, Any]:
    yf = _import_yfinance()
    if yf is None:
        return {}
    sym = symbol.upper()
    try:
        info = yf.Ticker(sym).info or {}
    except Exception as exc:
        logger.warning("yfinance info failed for %s: %s", sym, exc)
        return {}
    return {
        "symbol": sym,
        "shortName": info.get("shortName") or info.get("longName") or "",
        "sector": info.get("sector", ""),
        "industry": info.get("industry", ""),
        "marketCap": info.get("marketCap"),
        "currentPrice": info.get("currentPrice") or info.get("regularMarketPrice"),
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
        "fiftyTwoWeekHigh": info.get("fiftyTwoWeekHigh"),
        "fiftyTwoWeekLow": info.get("fiftyTwoWeekLow"),
        "source": "yfinance",
    }


def _normalize(hist: pd.DataFrame) -> pd.DataFrame:
    if hist is None or hist.empty:
        return pd.DataFrame()
    df = hist.reset_index()
    rename = {
        "Date": "date",
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
