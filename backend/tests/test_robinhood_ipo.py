"""Robinhood IPO 20% buffer reservation."""
from __future__ import annotations

from integrations.robinhood.ipo import ROBINHOOD_IPO_BUFFER, compute_ipo_reserved_cash


def test_ipo_buffer_five_shares_at_135():
    assert compute_ipo_reserved_cash(shares=5, list_price=135) == 810.0


def test_ipo_buffer_constant():
    assert ROBINHOOD_IPO_BUFFER == 1.2
