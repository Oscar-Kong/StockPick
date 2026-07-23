"""Yahoo Finance fallback for US equity OHLC when paid APIs are blocked or slow."""
from __future__ import annotations

import logging
import time
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

_MIN_CHUNK_TIMEOUT = 0.5


def _import_yfinance():
    try:
        import yfinance as yf

        return yf
    except ImportError:
        logger.debug("yfinance not installed — OHLC fallback unavailable")
        return None


def _is_rate_limit_error(exc: BaseException) -> bool:
    text = str(exc).lower()
    return "too many requests" in text or "rate limit" in text or "ratelimit" in text


def _yf_download_chunk(tickers: str, yf_period: str) -> Any:
    """Top-level worker for process-isolated Yahoo batch downloads (must be picklable)."""
    yf = _import_yfinance()
    if yf is None:
        return None
    return yf.download(
        tickers,
        period=yf_period,
        group_by="ticker",
        auto_adjust=True,
        threads=True,
        progress=False,
    )


def _yf_history_worker(symbol: str, yf_period: str) -> Any:
    """Top-level worker for process-isolated single-symbol history."""
    yf = _import_yfinance()
    if yf is None:
        return None
    return yf.Ticker(symbol).history(period=yf_period, auto_adjust=True)


def _yf_info_worker(symbol: str) -> dict[str, Any]:
    """Top-level worker for process-isolated Ticker.info (must be picklable)."""
    yf = _import_yfinance()
    if yf is None:
        return {}
    info = yf.Ticker(symbol).info or {}
    return {
        "symbol": symbol,
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


def _info_timeout_seconds() -> float:
    try:
        from config import YFINANCE_INFO_TIMEOUT_SECONDS

        return max(0.5, float(YFINANCE_INFO_TIMEOUT_SECONDS))
    except Exception:
        return 8.0


def get_history(symbol: str, period: str = "1y") -> pd.DataFrame:
    if _import_yfinance() is None:
        return pd.DataFrame()
    sym = symbol.upper()
    yf_period = _PERIOD_TO_YF.get(period, period)
    try:
        from utils.process_timeout import run_with_process_timeout

        hist = run_with_process_timeout(
            _yf_history_worker,
            sym,
            yf_period,
            timeout=_info_timeout_seconds(),
        )
        return _normalize(hist)
    except TimeoutError:
        logger.warning("yfinance history timed out for %s", sym)
        return pd.DataFrame()
    except Exception as exc:
        logger.warning("yfinance history failed for %s: %s", sym, exc)
        return pd.DataFrame()


def download_batch(
    symbols: list[str],
    period: str = "6mo",
    *,
    max_runtime_seconds: float | None = None,
) -> dict[str, pd.DataFrame]:
    """Batch OHLC via yfinance.download — much faster than per-symbol API calls.

    Honors ``max_runtime_seconds`` as a hard monotonic deadline and stops early on
    rate-limit errors so Stage A cannot hang indefinitely when Yahoo throttles.
    """
    if _import_yfinance() is None or not symbols:
        return {}
    unique = list(dict.fromkeys(s.upper() for s in symbols if s))
    yf_period = _PERIOD_TO_YF.get(period, period)
    result: dict[str, pd.DataFrame] = {}
    chunk_size = 40
    deadline: float | None = None
    if max_runtime_seconds and max_runtime_seconds > 0:
        deadline = time.monotonic() + float(max_runtime_seconds)

    for i in range(0, len(unique), chunk_size):
        if deadline is not None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                logger.warning(
                    "yfinance batch hit runtime deadline after %s/%s symbols",
                    len(result),
                    len(unique),
                )
                break
        else:
            remaining = 20.0

        chunk = unique[i : i + chunk_size]
        tickers = " ".join(chunk)
        # Never extend past the deadline with a minimum floor.
        chunk_timeout = min(20.0, remaining) if deadline is not None else 20.0
        if chunk_timeout < _MIN_CHUNK_TIMEOUT:
            logger.warning(
                "yfinance batch skipped remaining chunks — only %.2fs left of deadline",
                chunk_timeout,
            )
            break
        try:
            from utils.process_timeout import run_with_process_timeout

            raw = run_with_process_timeout(
                _yf_download_chunk,
                tickers,
                yf_period,
                timeout=chunk_timeout,
            )
        except TimeoutError:
            logger.warning(
                "yfinance batch chunk timed out after %.0fs (%s symbols)",
                chunk_timeout,
                len(chunk),
            )
            break
        except Exception as exc:
            logger.warning("yfinance batch download failed: %s", exc)
            if _is_rate_limit_error(exc):
                logger.warning("yfinance rate-limited — stopping remaining batch chunks")
                break
            continue
        if raw is None or getattr(raw, "empty", True):
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
    if _import_yfinance() is None:
        return {}
    sym = symbol.upper()
    try:
        from utils.process_timeout import run_with_process_timeout

        info = run_with_process_timeout(
            _yf_info_worker,
            sym,
            timeout=_info_timeout_seconds(),
        )
        return info if isinstance(info, dict) else {}
    except TimeoutError:
        logger.warning("yfinance info timed out for %s", sym)
        return {}
    except Exception as exc:
        logger.warning("yfinance info failed for %s: %s", sym, exc)
        return {}


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
