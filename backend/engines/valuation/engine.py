"""Valuation engine — DCF, relative multiples, reverse DCF."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def _safe(val: Any, default: float = 0.0) -> float:
    try:
        if val is None:
            return default
        v = float(val)
        return default if v != v else v
    except (TypeError, ValueError):
        return default


@dataclass
class ValuationResult:
    dcf_fair_value: float | None = None
    dcf_bull: float | None = None
    dcf_bear: float | None = None
    peer_fair_value: float | None = None
    reverse_dcf_implied_growth_pct: float | None = None
    reverse_dcf_implied_margin_pct: float | None = None
    margin_of_safety_pct: float | None = None
    premium_to_peers_pct: float | None = None
    valuation_score: float = 50.0
    verdict: str = "fair"
    assumptions: dict[str, Any] = field(default_factory=dict)
    sensitivity_grid: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "dcf_fair_value": self.dcf_fair_value,
            "dcf_bull": self.dcf_bull,
            "dcf_bear": self.dcf_bear,
            "peer_fair_value": self.peer_fair_value,
            "reverse_dcf_implied_growth_pct": self.reverse_dcf_implied_growth_pct,
            "reverse_dcf_implied_margin_pct": self.reverse_dcf_implied_margin_pct,
            "margin_of_safety_pct": self.margin_of_safety_pct,
            "premium_to_peers_pct": self.premium_to_peers_pct,
            "valuation_score": self.valuation_score,
            "verdict": self.verdict,
            "assumptions": self.assumptions,
            "sensitivity_grid": self.sensitivity_grid,
        }


def _verdict_from_mos(mos_pct: float | None, premium_pct: float | None) -> str:
    if mos_pct is not None:
        if mos_pct >= 15:
            return "cheap"
        if mos_pct >= 5:
            return "fair"
        if mos_pct >= -10:
            return "expensive"
        return "extremely_expensive"
    if premium_pct is not None:
        if premium_pct <= -10:
            return "cheap"
        if premium_pct <= 10:
            return "fair"
        if premium_pct <= 30:
            return "expensive"
        return "extremely_expensive"
    return "fair"


def _score_from_verdict(verdict: str) -> float:
    return {
        "cheap": 82.0,
        "fair": 58.0,
        "expensive": 35.0,
        "extremely_expensive": 18.0,
    }.get(verdict, 50.0)


def run_dcf(
    *,
    revenue: float,
    operating_margin: float,
    tax_rate: float = 0.21,
    reinvestment_rate: float = 0.35,
    wacc: float = 0.10,
    terminal_growth: float = 0.025,
    net_debt: float = 0.0,
    shares: float,
    growth_years: int = 5,
    revenue_cagr: float = 0.08,
) -> tuple[float, float, float]:
    """Simple 5-stage FCF DCF returning base, bull, bear fair values per share."""
    if shares <= 0 or revenue <= 0:
        return 0.0, 0.0, 0.0

    def _dcf(cagr: float, margin: float, term_g: float) -> float:
        fcf_sum = 0.0
        rev = revenue
        for yr in range(1, growth_years + 1):
            rev *= 1 + cagr
            op_inc = rev * margin
            nopat = op_inc * (1 - tax_rate)
            reinvest = nopat * reinvestment_rate
            fcf = nopat - reinvest
            fcf_sum += fcf / ((1 + wacc) ** yr)
        terminal_fcf = (rev * (1 + cagr) * margin * (1 - tax_rate) * (1 - reinvestment_rate))
        terminal_val = terminal_fcf * (1 + term_g) / max(wacc - term_g, 0.01)
        pv_terminal = terminal_val / ((1 + wacc) ** growth_years)
        equity = fcf_sum + pv_terminal - net_debt
        return max(0.0, equity / shares)

    base = _dcf(revenue_cagr, operating_margin, terminal_growth)
    bull = _dcf(revenue_cagr + 0.05, min(operating_margin + 0.03, 0.45), terminal_growth + 0.005)
    bear = _dcf(max(revenue_cagr - 0.05, 0.0), max(operating_margin - 0.03, 0.05), terminal_growth - 0.005)
    return round(base, 2), round(bull, 2), round(bear, 2)


def run_relative_valuation(
    *,
    price: float,
    forward_pe: float | None,
    peer_median_pe: float | None,
    ev_ebitda: float | None = None,
    peer_ev_ebitda: float | None = None,
    eps: float | None = None,
) -> tuple[float | None, float | None]:
    """Peer-relative fair value and premium/discount %."""
    fair: float | None = None
    premium: float | None = None

    if forward_pe and peer_median_pe and peer_median_pe > 0 and eps and eps > 0:
        fair = round(peer_median_pe * eps, 2)
        premium = round((forward_pe / peer_median_pe - 1) * 100, 2)
    elif ev_ebitda and peer_ev_ebitda and peer_ev_ebitda > 0:
        premium = round((ev_ebitda / peer_ev_ebitda - 1) * 100, 2)
        if price and premium is not None:
            fair = round(price / (1 + premium / 100), 2)

    return fair, premium


def reverse_dcf_implied_growth(
    *,
    price: float,
    revenue: float,
    operating_margin: float,
    shares: float,
    wacc: float = 0.10,
    terminal_growth: float = 0.025,
    tax_rate: float = 0.21,
    reinvestment_rate: float = 0.35,
) -> tuple[float | None, float | None]:
    """Binary search for revenue CAGR implied by current price."""
    if price <= 0 or revenue <= 0 or shares <= 0:
        return None, None

    lo, hi = -0.05, 0.40
    target = price
    for _ in range(24):
        mid = (lo + hi) / 2
        base, _, _ = run_dcf(
            revenue=revenue,
            operating_margin=operating_margin,
            wacc=wacc,
            terminal_growth=terminal_growth,
            tax_rate=tax_rate,
            reinvestment_rate=reinvestment_rate,
            shares=shares,
            revenue_cagr=mid,
        )
        if base > target:
            hi = mid
        else:
            lo = mid
    implied_growth = round((lo + hi) / 2 * 100, 2)
    return implied_growth, round(operating_margin * 100, 2)


def dcf_sensitivity_grid(
    *,
    revenue: float,
    operating_margin: float,
    shares: float,
    net_debt: float = 0.0,
    revenue_cagr: float = 0.08,
    wacc: float = 0.10,
    terminal_growth: float = 0.025,
) -> dict[str, Any]:
    """WACC × terminal growth fair-value grid (per share)."""
    if shares <= 0 or revenue <= 0:
        return {"wacc": [], "terminal_growth": [], "values": []}

    waccs = [round(wacc - 0.01, 4), round(wacc, 4), round(wacc + 0.01, 4), round(wacc + 0.02, 4)]
    terms = [
        round(max(0.005, terminal_growth - 0.005), 4),
        round(terminal_growth, 4),
        round(terminal_growth + 0.005, 4),
        round(terminal_growth + 0.01, 4),
    ]
    values: list[list[float | None]] = []
    for w in waccs:
        row: list[float | None] = []
        for t in terms:
            if w <= t:
                row.append(None)
                continue
            base, _, _ = run_dcf(
                revenue=revenue,
                operating_margin=operating_margin,
                net_debt=net_debt,
                shares=shares,
                revenue_cagr=revenue_cagr,
                wacc=w,
                terminal_growth=t,
            )
            row.append(base if base else None)
        values.append(row)
    return {"wacc": waccs, "terminal_growth": terms, "values": values}


def evaluate_valuation(info: dict[str, Any], fundamentals: dict[str, Any] | None = None, *, symbol: str | None = None) -> ValuationResult:
    fundamentals = fundamentals or {}
    sym = (symbol or info.get("symbol") or fundamentals.get("symbol") or "").upper()
    sector = info.get("sector") or fundamentals.get("sector")
    price = _safe(info.get("currentPrice") or info.get("regularMarketPrice") or fundamentals.get("price"))
    revenue = _safe(info.get("totalRevenue") or fundamentals.get("revenue_ttm"))
    shares = _safe(info.get("sharesOutstanding") or fundamentals.get("shares_outstanding"))
    if shares <= 0 and price > 0:
        mcap = _safe(info.get("marketCap") or fundamentals.get("marketCap"))
        if mcap > 0:
            shares = mcap / price

    op_margin = _safe(
        fundamentals.get("operating_margin") or info.get("operatingMargins"),
        default=0.15,
    )
    pe = _safe(info.get("trailingPE") or fundamentals.get("pe_ratio"))
    fwd_pe = _safe(info.get("forwardPE") or fundamentals.get("forward_pe"))
    sector_pe = _safe(fundamentals.get("sector_median_pe"), default=22.0)
    if sym:
        try:
            from engines.valuation.peers import peer_median_multiples, peer_symbols

            peers = peer_symbols(sym, sector)
            med = peer_median_multiples(peers)
            sector_pe = med.get("forward_pe") or med.get("pe") or sector_pe
        except Exception:
            pass
    eps = price / pe if price and pe and pe > 0 else None

    net_debt = _safe(fundamentals.get("net_debt"), default=0.0)
    wacc = 0.09 + min(0.04, _safe(info.get("beta"), default=1.0) * 0.02)

    base, bull, bear = run_dcf(
        revenue=revenue or price * shares * 0.1,
        operating_margin=max(op_margin, 0.05),
        net_debt=net_debt,
        shares=max(shares, 1.0),
        revenue_cagr=_safe(info.get("revenueGrowth"), default=0.08),
        wacc=wacc,
    )

    peer_fv, premium = run_relative_valuation(
        price=price,
        forward_pe=fwd_pe or pe,
        peer_median_pe=sector_pe,
        eps=eps,
    )

    implied_growth, implied_margin = reverse_dcf_implied_growth(
        price=price,
        revenue=revenue or price * shares * 0.1,
        operating_margin=max(op_margin, 0.05),
        shares=max(shares, 1.0),
        wacc=wacc,
    )

    mos = round((base / price - 1) * 100, 2) if base and price else None
    verdict = _verdict_from_mos(mos, premium)
    score = _score_from_verdict(verdict)
    rev_cagr = _safe(info.get("revenueGrowth"), default=0.08)
    sens_grid = dcf_sensitivity_grid(
        revenue=revenue or price * shares * 0.1,
        operating_margin=max(op_margin, 0.05),
        shares=max(shares, 1.0),
        net_debt=net_debt,
        revenue_cagr=rev_cagr,
        wacc=wacc,
    )

    return ValuationResult(
        dcf_fair_value=base if base else None,
        dcf_bull=bull if bull else None,
        dcf_bear=bear if bear else None,
        peer_fair_value=peer_fv,
        reverse_dcf_implied_growth_pct=implied_growth,
        reverse_dcf_implied_margin_pct=implied_margin,
        margin_of_safety_pct=mos,
        premium_to_peers_pct=premium,
        valuation_score=score,
        verdict=verdict,
        assumptions={
            "wacc": round(wacc, 4),
            "operating_margin": round(op_margin, 4),
            "sector_median_pe": sector_pe,
            "price": price,
            "sensitivity": {
                "wacc_bull": round(max(0.06, wacc - 0.01), 4),
                "wacc_bear": round(wacc + 0.015, 4),
                "growth_bull": round(rev_cagr + 0.03, 4),
                "growth_bear": round(max(0.0, rev_cagr - 0.03), 4),
            },
        },
        sensitivity_grid=sens_grid,
    )
