"""Transaction cost model — fees + slippage (bps on notional)."""
from __future__ import annotations

from config import BT_FEE_BPS_DEFAULT, BT_MIN_TICKET_USD, BT_SLIP_BPS_DEFAULT

SLEEVE_COST_BPS: dict[str, dict[str, float]] = {
    "penny": {"fee": 8.0, "slip": 15.0},
    "compounder": {"fee": 4.0, "slip": 8.0},
}


def resolve_cost_bps(sleeve: str | None = None) -> tuple[float, float]:
    from core.sleeve import normalize_sleeve

    key = normalize_sleeve(sleeve) if sleeve else None
    if key and key in SLEEVE_COST_BPS:
        cfg = SLEEVE_COST_BPS[key]
        return float(cfg["fee"]), float(cfg["slip"])
    return BT_FEE_BPS_DEFAULT, BT_SLIP_BPS_DEFAULT


def trade_cost_usd(
    notional: float,
    *,
    fee_bps: float | None = None,
    slip_bps: float | None = None,
    sleeve: str | None = None,
) -> float:
    """Round-trip cost estimate on traded notional."""
    if notional <= 0:
        return 0.0
    f_bps, s_bps = resolve_cost_bps(sleeve)
    fee_bps = fee_bps if fee_bps is not None else f_bps
    slip_bps = slip_bps if slip_bps is not None else s_bps
    cost = notional * (fee_bps + slip_bps) / 10_000.0
    return max(BT_MIN_TICKET_USD, cost) if notional > 0 else 0.0
