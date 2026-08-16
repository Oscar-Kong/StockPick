"""Deterministic intraday state evaluation for active positions.

This module consumes locally available snapshots. It performs no provider fetches
and never places an order.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

PositionState = Literal[
    "HOLD",
    "ADD_SETUP",
    "ADD_CONFIRMED",
    "TRIM",
    "EXIT_WARNING",
    "EXIT",
    "DATA_STALE",
]


@dataclass(frozen=True)
class PositionSnapshot:
    symbol: str
    price: float
    quote_age_seconds: float
    stop_price: float | None = None
    target_price: float | None = None
    vwap: float | None = None
    confirmation_bars: int = 0
    max_quote_age_seconds: float = 120.0


@dataclass(frozen=True)
class PositionEvaluation:
    symbol: str
    state: PositionState
    actionable: bool
    evidence: list[str] = field(default_factory=list)


def evaluate_intraday_position(snapshot: PositionSnapshot) -> PositionEvaluation:
    """Evaluate one snapshot using explicit priority-ordered safety rules."""
    symbol = snapshot.symbol.upper()
    if (
        snapshot.price <= 0
        or snapshot.quote_age_seconds < 0
        or snapshot.quote_age_seconds > snapshot.max_quote_age_seconds
    ):
        return PositionEvaluation(
            symbol=symbol,
            state="DATA_STALE",
            actionable=False,
            evidence=[f"Quote age {snapshot.quote_age_seconds:.0f}s exceeds freshness policy"],
        )

    if snapshot.stop_price is not None and snapshot.stop_price > 0:
        if snapshot.price <= snapshot.stop_price and snapshot.confirmation_bars >= 2:
            return PositionEvaluation(
                symbol=symbol,
                state="EXIT",
                actionable=True,
                evidence=["Stop/invalidation breach confirmed for two bars"],
            )
        distance_pct = (snapshot.price / snapshot.stop_price - 1.0) * 100.0
        if distance_pct <= 2.0:
            return PositionEvaluation(
                symbol=symbol,
                state="EXIT_WARNING",
                actionable=False,
                evidence=[f"Price is {distance_pct:.1f}% above stop/invalidation"],
            )

    if snapshot.target_price is not None and snapshot.target_price > 0:
        if snapshot.price >= snapshot.target_price:
            return PositionEvaluation(
                symbol=symbol,
                state="TRIM",
                actionable=True,
                evidence=["Target price reached"],
            )

    if snapshot.vwap is not None and snapshot.vwap > 0:
        if snapshot.price > snapshot.vwap and snapshot.confirmation_bars >= 2:
            return PositionEvaluation(
                symbol=symbol,
                state="ADD_CONFIRMED",
                actionable=True,
                evidence=["Price held above VWAP for two bars"],
            )
        if snapshot.price > snapshot.vwap:
            return PositionEvaluation(
                symbol=symbol,
                state="ADD_SETUP",
                actionable=False,
                evidence=["Price is above VWAP; confirmation pending"],
            )

    return PositionEvaluation(
        symbol=symbol,
        state="HOLD",
        actionable=False,
        evidence=["No configured state boundary crossed"],
    )
