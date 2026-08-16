"""Deterministic intraday state evaluation for active positions.

This module consumes locally available snapshots. It performs no provider fetches
and never places an order.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
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
    volume_confirmed: bool = False
    spread_confirmed: bool = False
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
        if (
            snapshot.price > snapshot.vwap
            and snapshot.confirmation_bars >= 2
            and snapshot.volume_confirmed
            and snapshot.spread_confirmed
        ):
            return PositionEvaluation(
                symbol=symbol,
                state="ADD_CONFIRMED",
                actionable=True,
                evidence=["VWAP, volume and spread confirmation passed for two bars"],
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


@dataclass(frozen=True)
class ActivePositionStatus:
    symbol: str
    bucket: str
    state: PositionState
    actionable: bool
    price: float | None
    quote_as_of: str | None
    quote_age_seconds: float | None
    data_status: str
    shares: float
    avg_cost: float
    unrealized_pl_pct: float | None
    stop_price: float | None
    target_price: float | None
    distance_to_stop_pct: float | None
    distance_to_target_pct: float | None
    evidence: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PositionTransition:
    symbol: str
    from_state: str | None
    to_state: PositionState
    actionable: bool
    evidence: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ActiveMonitorResult:
    as_of: str
    statuses: list[ActivePositionStatus]
    transitions: list[PositionTransition]


def _parse_as_of(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None


class ActivePositionMonitor:
    """Pure portfolio evaluator; callers own quote ingestion and persistence."""

    def __init__(
        self,
        *,
        stop_loss_pct: float = 0.05,
        target_gain_pct: float = 0.10,
        max_quote_age_seconds: float = 120.0,
        min_confirmation_seconds: float = 240.0,
    ) -> None:
        self.stop_loss_pct = stop_loss_pct
        self.target_gain_pct = target_gain_pct
        self.max_quote_age_seconds = max_quote_age_seconds
        self.min_confirmation_seconds = min_confirmation_seconds

    def evaluate(
        self,
        *,
        holdings: list[dict],
        quotes: dict[str, dict],
        previous_states: dict[str, str],
        previous_state_times: dict[str, str] | None = None,
        now: datetime | None = None,
    ) -> ActiveMonitorResult:
        now_utc = now or datetime.now(timezone.utc)
        if now_utc.tzinfo is None:
            now_utc = now_utc.replace(tzinfo=timezone.utc)
        now_utc = now_utc.astimezone(timezone.utc)
        statuses: list[ActivePositionStatus] = []
        transitions: list[PositionTransition] = []
        previous_state_times = previous_state_times or {}

        for holding in holdings:
            symbol = str(holding.get("symbol") or "").upper()
            if not symbol:
                continue
            shares = float(holding.get("shares") or 0.0)
            avg_cost = float(holding.get("avg_cost") or 0.0)
            bucket = str(holding.get("bucket") or "penny")
            quote = quotes.get(symbol) or {}
            raw_price = quote.get("price")
            price = float(raw_price) if isinstance(raw_price, (int, float)) and raw_price > 0 else None
            quote_dt = _parse_as_of(quote.get("as_of"))
            quote_age = max(0.0, (now_utc - quote_dt).total_seconds()) if quote_dt else None
            if price is None:
                data_status = "missing_quote"
            elif quote_age is None:
                data_status = "missing_timestamp"
            elif quote_age > self.max_quote_age_seconds:
                data_status = "stale_quote"
            else:
                data_status = "fresh"

            is_penny = bucket.lower() == "penny"
            stop_price = avg_cost * (1.0 - self.stop_loss_pct) if avg_cost > 0 and is_penny else None
            target_price = avg_cost * (1.0 + self.target_gain_pct) if avg_cost > 0 and is_penny else None
            previous = previous_states.get(symbol)
            previous_at = _parse_as_of(previous_state_times.get(symbol))
            sample_spacing_ok = bool(
                previous_at
                and (now_utc - previous_at).total_seconds() >= self.min_confirmation_seconds
            )
            confirmed_stop_breach = bool(
                previous in {"EXIT_WARNING", "EXIT"}
                and price is not None
                and stop_price is not None
                and price <= stop_price
                and (previous == "EXIT" or sample_spacing_ok)
            )
            evaluation = evaluate_intraday_position(
                PositionSnapshot(
                    symbol=symbol,
                    price=price or 0.0,
                    quote_age_seconds=(
                        quote_age if quote_age is not None else self.max_quote_age_seconds + 1.0
                    ),
                    stop_price=stop_price,
                    target_price=target_price,
                    confirmation_bars=2 if confirmed_stop_breach else 0,
                    max_quote_age_seconds=self.max_quote_age_seconds,
                )
            )
            unrealized_pl_pct = (
                round((price / avg_cost - 1.0) * 100.0, 2)
                if price is not None and avg_cost > 0
                else None
            )
            distance_to_stop_pct = (
                round((price / stop_price - 1.0) * 100.0, 2)
                if price is not None and stop_price
                else None
            )
            distance_to_target_pct = (
                round((target_price / price - 1.0) * 100.0, 2)
                if price is not None and target_price
                else None
            )
            status = ActivePositionStatus(
                symbol=symbol,
                bucket=bucket,
                state=evaluation.state,
                actionable=evaluation.actionable,
                price=price,
                quote_as_of=quote_dt.isoformat() if quote_dt else None,
                quote_age_seconds=round(quote_age, 1) if quote_age is not None else None,
                data_status=data_status,
                shares=shares,
                avg_cost=avg_cost,
                unrealized_pl_pct=unrealized_pl_pct,
                stop_price=round(stop_price, 4) if stop_price else None,
                target_price=round(target_price, 4) if target_price else None,
                distance_to_stop_pct=distance_to_stop_pct,
                distance_to_target_pct=distance_to_target_pct,
                evidence=evaluation.evidence,
            )
            statuses.append(status)
            if previous != evaluation.state:
                transitions.append(
                    PositionTransition(
                        symbol=symbol,
                        from_state=previous,
                        to_state=evaluation.state,
                        actionable=evaluation.actionable,
                        evidence=evaluation.evidence,
                    )
                )

        return ActiveMonitorResult(
            as_of=now_utc.isoformat(),
            statuses=statuses,
            transitions=transitions,
        )
