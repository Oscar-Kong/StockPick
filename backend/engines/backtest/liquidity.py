"""Liquidity constraints — max participation of 20d average dollar volume."""
from __future__ import annotations

import pandas as pd

from config import BT_PARTICIPATION_RATE


def avg_dollar_volume(hist: pd.DataFrame, window: int = 20) -> float:
    if hist is None or hist.empty or len(hist) < 5:
        return 0.0
    tail = hist.tail(window)
    vol = tail["volume"].astype(float)
    close = tail["close"].astype(float)
    return float((vol * close).mean())


def cap_rebalance_notional(
    symbol: str,
    desired_notional: float,
    price: float,
    hist: pd.DataFrame | None,
    *,
    participation_rate: float | None = None,
) -> tuple[float, str | None]:
    """Return executable notional capped by ADV participation."""
    rate = participation_rate if participation_rate is not None else BT_PARTICIPATION_RATE
    adv = avg_dollar_volume(hist) if hist is not None else 0.0
    if adv <= 0 or price <= 0:
        return desired_notional, None
    cap = adv * rate
    if desired_notional <= cap:
        return desired_notional, None
    return cap, f"{symbol}: capped to {rate*100:.0f}% of 20d ADV"
