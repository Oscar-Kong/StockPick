"""Portfolio impact — sector exposure and correlation proxy."""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from config import DEFAULT_ACTIVE_POSITIONS, DEFAULT_PORTFOLIO_EXPOSURE
from data.price_service import PriceService
from services.holdings_loader import load_holdings


def estimate_portfolio_impact(
    symbol: str,
    *,
    sector: str | None = None,
    recommended_weight_pct: float = 0.0,
    holdings: list[str] | None = None,
) -> dict[str, Any]:
    """Estimate correlation with portfolio and sector exposure after trade."""
    ps = PriceService()
    sym = symbol.upper()
    holdings_source = "explicit"
    if holdings is None:
        holdings, holdings_source = load_holdings(prefer_journal=True)
    holdings = [h.upper() for h in holdings if h.upper() != sym][:12]

    corr_with_portfolio = None
    if holdings:
        try:
            rets: list[pd.Series] = []
            target = ps.get_history(sym, period="6mo")
            if not target.empty:
                target_r = target["close"].pct_change().dropna()
                rets.append(target_r)
                for h in holdings:
                    hdf = ps.get_history(h, period="6mo")
                    if not hdf.empty:
                        rets.append(hdf["close"].pct_change().dropna())
            if len(rets) >= 2:
                df = pd.concat(rets, axis=1).dropna()
                if len(df) >= 20:
                    corr_with_portfolio = round(float(df.corr().iloc[0, 1:].mean()), 3)
        except Exception:
            pass

    sector_exposure_after = None
    if sector and recommended_weight_pct:
        base_sector_pct = DEFAULT_PORTFOLIO_EXPOSURE * 100 / max(DEFAULT_ACTIVE_POSITIONS, 1)
        sector_exposure_after = round(base_sector_pct + recommended_weight_pct, 2)

    beta_proxy = None
    try:
        stock = ps.get_history(sym, period="1y")
        spy = ps.get_spy_history(period="1y")
        if not stock.empty and not spy.empty:
            sr = stock["close"].pct_change().dropna()
            sp = spy["close"].pct_change().dropna()
            joined = pd.concat([sr, sp], axis=1).dropna()
            if len(joined) >= 60:
                cov = np.cov(joined.iloc[:, 0], joined.iloc[:, 1])
                if cov[1, 1] > 0:
                    beta_proxy = round(float(cov[0, 1] / cov[1, 1]), 2)
    except Exception:
        pass

    return {
        "symbol": sym,
        "sector": sector,
        "correlation_with_portfolio": corr_with_portfolio,
        "sector_exposure_after_pct": sector_exposure_after,
        "portfolio_beta_impact": beta_proxy,
        "recommended_weight_pct": recommended_weight_pct,
        "holdings_source": holdings_source,
        "holdings_used": holdings,
    }
