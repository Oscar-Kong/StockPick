"""Sector ETF relative strength vs SPY."""
from __future__ import annotations

import pandas as pd

from data.market_data_client import MarketDataClient
from data.sector_map import sector_etf
from scoring.technical import momentum_score, relative_strength_vs_spy


_etf_cache: dict[str, pd.DataFrame] = {}


def _get_etf_history(etf: str, market: MarketDataClient, period: str = "6mo") -> pd.DataFrame:
    if etf not in _etf_cache:
        _etf_cache[etf] = market.get_history(etf, period=period)
    return _etf_cache[etf]


def sector_relative_strength(
    stock_df: pd.DataFrame,
    sector: str | None,
    spy_df: pd.DataFrame,
    market: MarketDataClient | None = None,
    days: int = 20,
) -> float:
    """Score 0-100: stock RS vs sector ETF, blended with sector ETF RS vs SPY."""
    market = market or MarketDataClient()
    stock_vs_spy = relative_strength_vs_spy(stock_df, spy_df, days=days)

    etf_symbol = sector_etf(sector)
    if not etf_symbol:
        return stock_vs_spy

    sector_df = _get_etf_history(etf_symbol, market)
    if sector_df.empty:
        return stock_vs_spy

    stock_vs_sector = relative_strength_vs_spy(stock_df, sector_df, days=days)
    sector_vs_spy = relative_strength_vs_spy(sector_df, spy_df, days=days)
    market_tailwind = momentum_score(spy_df, days=days)

    return max(
        0.0,
        min(100.0, stock_vs_sector * 0.45 + sector_vs_spy * 0.35 + market_tailwind * 0.20),
    )
