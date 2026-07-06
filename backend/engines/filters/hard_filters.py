"""Hard filter registry — table-driven rules per sleeve (Phase 3)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal

from config import (
    HARD_FILTERS_V3_ENABLED,
    PENNY_MIN_DOLLAR_VOLUME_20D,
    PENNY_PRICE_MIN,
)
from data.price_service import avg_dollar_volume_from_history
from models.schemas import ScanOptions
from scoring.metrics import safe_float
from screeners.base import CandidateContext

Action = Literal["exclude", "cap_score"]


@dataclass(frozen=True)
class HardFilterRule:
    filter_id: str
    sleeve: str
    action: Action
    description: str
    check: Callable[[CandidateContext, ScanOptions], tuple[bool, str]]


def _penny_liquidity(ctx: CandidateContext, _options: ScanOptions) -> tuple[bool, str]:
    dv = avg_dollar_volume_from_history(ctx.history)
    if dv < PENNY_MIN_DOLLAR_VOLUME_20D:
        return False, f"Dollar volume ${dv:,.0f} < min ${PENNY_MIN_DOLLAR_VOLUME_20D:,.0f}"
    return True, ""


def _penny_delisting(ctx: CandidateContext, _options: ScanOptions) -> tuple[bool, str]:
    df = ctx.history
    if df is None or df.empty or len(df) < 30:
        return True, ""
    tail = df["close"].tail(30)
    if (tail < 1.0).all():
        return False, "Price below $1 (delisting risk) for 30 sessions"
    return True, ""


def _penny_otc(ctx: CandidateContext, _options: ScanOptions) -> tuple[bool, str]:
    exchange = (ctx.info.get("exchange") or ctx.info.get("fullExchangeName") or "").upper()
    if "OTC" in exchange or "PINK" in exchange:
        return False, f"OTC listing ({exchange})"
    return True, ""


def _penny_losses(ctx: CandidateContext, _options: ScanOptions) -> tuple[bool, str]:
    eps = safe_float(ctx.info.get("trailingEps") or ctx.fundamentals.get("eps"))
    earnings = ctx.info.get("earningsQuarterlyGrowth")
    if eps < 0 and safe_float(earnings) < 0:
        return False, "Persistent losses (negative EPS and earnings growth)"
    return True, ""



def _compounder_adjusted_eps(ctx: CandidateContext, _options: ScanOptions) -> tuple[bool, str]:
    from scoring.compounder_v3 import adjusted_eps_score

    if adjusted_eps_score(ctx.info, ctx.fundamentals) < 35:
        return False, "Adjusted EPS quality too low (one-off distortion)"
    return True, ""


def _compounder_fcf(ctx: CandidateContext, _options: ScanOptions) -> tuple[bool, str]:
    fcf = safe_float(ctx.info.get("freeCashflow") or ctx.fundamentals.get("free_cash_flow"))
    debt = safe_float(ctx.info.get("debtToEquity") or ctx.fundamentals.get("debt_to_equity"))
    if fcf < 0 and debt > 200:
        return False, "Negative FCF with high leverage"
    return True, ""


HARD_FILTER_TABLE: list[HardFilterRule] = [
    HardFilterRule("liquidity", "penny", "exclude", "20d dollar volume", _penny_liquidity),
    HardFilterRule("delisting_risk", "penny", "exclude", "Sustained sub-$1 price", _penny_delisting),
    HardFilterRule("st_status", "penny", "exclude", "OTC / pink sheet", _penny_otc),
    HardFilterRule("persistent_losses", "penny", "exclude", "Negative EPS trajectory", _penny_losses),
    HardFilterRule("adjusted_eps", "compounder", "exclude", "EPS one-off filter", _compounder_adjusted_eps),
    HardFilterRule("fcf_leverage", "compounder", "exclude", "FCF vs debt", _compounder_fcf),
]


@dataclass
class HardFilterResult:
    passed: bool
    failed_rules: list[str]
    cap_score_at: float | None = None


def evaluate_hard_filters(
    sleeve: str,
    ctx: CandidateContext,
    options: ScanOptions | None = None,
) -> HardFilterResult:
    if not HARD_FILTERS_V3_ENABLED:
        return HardFilterResult(passed=True, failed_rules=[])

    options = options or ScanOptions()
    failed: list[str] = []
    cap: float | None = None

    for rule in HARD_FILTER_TABLE:
        if rule.sleeve != sleeve:
            continue
        ok, reason = rule.check(ctx, options)
        if ok:
            continue
        label = f"{rule.filter_id}: {reason}" if reason else rule.filter_id
        if rule.action == "exclude":
            return HardFilterResult(passed=False, failed_rules=[label], cap_score_at=None)
        failed.append(label)
        cap = 40.0

    return HardFilterResult(passed=True, failed_rules=failed, cap_score_at=cap)


def apply_hard_filters_to_context(ctx: CandidateContext, result: HardFilterResult) -> None:
    if result.cap_score_at is not None:
        ctx.info["_hard_filter_score_cap"] = result.cap_score_at
    if result.failed_rules:
        ctx.info["_hard_filter_failures"] = result.failed_rules
