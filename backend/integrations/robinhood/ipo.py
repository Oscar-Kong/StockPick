"""Robinhood IPO order cash reservation (20% price buffer)."""
from __future__ import annotations

ROBINHOOD_IPO_BUFFER = 1.2


def compute_ipo_reserved_cash(
    *,
    shares: float,
    list_price: float,
    buffer: float = ROBINHOOD_IPO_BUFFER,
) -> float:
    """
    Cash Robinhood holds for an upcoming IPO order.

    Robinhood reserves up to list_price × (1 + buffer_pct) per share so the fill
    can complete if the IPO prices above the indicated range. Default buffer is 20%.
    """
    return round(max(0.0, float(shares)) * max(0.0, float(list_price)) * float(buffer), 2)
