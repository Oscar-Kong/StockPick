"""Daily portfolio decision support — deterministic rule engine."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Literal

from buckets import DEFAULT_BUCKET, resolve_bucket
from config import SLEEVE_MAX_WEIGHT
from data.historical_store import HistoricalStore
from data.portfolio_store import DEFAULT_ACCOUNT_ID, save_decision_snapshot
from data.price_service import PriceService
from data.reconciler import DataReconciler
from models.schemas import (
    PortfolioDecisionItem,
    PortfolioDecisionRequest,
    PortfolioDecisionResponse,
)
from services.quant_risk_sizing_service import build_unified_risk, sizing_from_score_context
from services.quant_v2_service import build_v2_score

logger = logging.getLogger(__name__)

DecisionType = Literal["buy", "keep", "trim", "sell", "watch"]

# Penny: tighter triggers
_PENNY_SELL_SCORE = 38
_PENNY_TRIM_SCORE = 52
_PENNY_RISK_SELL = 72
_PENNY_RISK_TRIM = 58
_PENNY_OVERWEIGHT_MULT = 1.15

# Compounder: slower-moving
_COMPO_SELL_SCORE = 40
_COMPO_TRIM_SCORE = 50
_COMPO_RISK_SELL = 78
_COMPO_RISK_TRIM = 65
_COMPO_OVERWEIGHT_MULT = 1.25


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _action_pcts(decision: DecisionType) -> tuple[float, float, float]:
    """Return (buy_pct, keep_pct, sell_pct) summing to 100."""
    table: dict[DecisionType, tuple[float, float, float]] = {
        "buy": (45.0, 45.0, 10.0),
        "keep": (15.0, 70.0, 15.0),
        "trim": (5.0, 35.0, 60.0),
        "sell": (0.0, 15.0, 85.0),
        "watch": (10.0, 60.0, 30.0),
    }
    return table[decision]


def _score_context(symbol: str, sleeve: str) -> dict:
    """Fetch score, risk, sizing for one symbol."""
    score_res = build_v2_score(
        symbol,
        sleeve,
        validate_parity=False,
        include_sizing=False,
        persist_snapshot=False,
    )
    if isinstance(score_res, dict) and score_res.get("error"):
        return {"error": score_res.get("error"), "score": 50.0, "risk_index": 50.0}

    rec = DataReconciler().reconcile(symbol)
    dq = rec.quality_score if rec else None
    risk_index = score_res.risk.risk_score if score_res.risk else 50.0

    risk = build_unified_risk(symbol, sleeve, score_result=score_res)
    risk_index = risk.risk_index if hasattr(risk, "risk_index") else risk_index

    active_n = max(1, 8)
    sizing = sizing_from_score_context(
        symbol,
        sleeve,
        final_score=score_res.score,
        data_quality_score=dq,
        risk_index=risk_index,
        active_positions=active_n,
        persist=False,
    )
    target_w = (sizing.recommended_weight_pct / 100.0) if sizing else SLEEVE_MAX_WEIGHT.get(sleeve, 0.05)

    risk_flags: list[str] = []
    if dq is not None and dq < 45:
        risk_flags.append("low_data_quality")
    if risk_index >= 65:
        risk_flags.append("elevated_risk_index")
    if hasattr(risk, "alerts"):
        for a in (risk.alerts or [])[:3]:
            msg = a.get("message") if isinstance(a, dict) else str(a)
            if msg:
                risk_flags.append(msg[:80])

    return {
        "score": float(score_res.score),
        "risk_index": float(risk_index),
        "target_weight": float(target_w),
        "dq": dq,
        "risk_flags": risk_flags,
        "recommendation": getattr(score_res.recommendation, "action", None) if score_res.recommendation else None,
    }


def _decide(
    *,
    sleeve: str,
    score: float,
    risk_index: float,
    current_weight: float,
    target_weight: float,
    dq: float | None,
) -> tuple[DecisionType, list[str]]:
    reasons: list[str] = []
    max_w = float(SLEEVE_MAX_WEIGHT.get(sleeve, 0.08))
    overweight = current_weight > min(max_w * (1.15 if sleeve == "penny" else 1.25), target_weight * 1.2 + 0.005)

    if sleeve == "penny":
        if score <= _PENNY_SELL_SCORE or risk_index >= _PENNY_RISK_SELL:
            reasons.append(f"Penny score {score:.0f} or risk {risk_index:.0f} triggers exit")
            return "sell", reasons
        if overweight or score <= _PENNY_TRIM_SCORE or risk_index >= _PENNY_RISK_TRIM:
            if overweight:
                reasons.append(f"Weight {current_weight*100:.1f}% above penny cap")
            if score <= _PENNY_TRIM_SCORE:
                reasons.append(f"Score {score:.0f} below trim threshold")
            return "trim", reasons
        if current_weight < target_weight * 0.85 and score >= 62:
            reasons.append(f"Score {score:.0f} supports adding toward {target_weight*100:.1f}% target")
            return "buy", reasons
        if dq is not None and dq < 40:
            reasons.append("Data quality too low for penny add")
            return "watch", reasons
        reasons.append("Penny position within score and risk bands")
        return "keep", reasons

    # compounder
    if score <= _COMPO_SELL_SCORE and risk_index >= _COMPO_RISK_TRIM:
        reasons.append("Compounder score and risk both weak — consider exit")
        return "sell", reasons
    if overweight and score <= _COMPO_TRIM_SCORE:
        reasons.append("Overweight vs target with fading score")
        return "trim", reasons
    if risk_index >= _COMPO_RISK_SELL:
        reasons.append(f"Risk index {risk_index:.0f} elevated for compounder")
        return "trim", reasons
    if current_weight < target_weight * 0.75 and score >= 68:
        reasons.append(f"Quality score {score:.0f} — room to add toward target")
        return "buy", reasons
    if score < _COMPO_TRIM_SCORE:
        reasons.append("Hold but monitor — score below add threshold")
        return "watch", reasons
    reasons.append("Compounder hold — short-term noise discounted")
    return "keep", reasons


def _last_price(ps: PriceService, symbol: str) -> float | None:
    df = ps.get_history(symbol, period="5d")
    if df is None or df.empty:
        return None
    return float(df["close"].iloc[-1])


def run_portfolio_daily_decision(body: PortfolioDecisionRequest) -> PortfolioDecisionResponse:
    ps = PriceService()
    cash = max(0.0, float(body.cash))
    notes: list[str] = []

    priced: list[dict] = []
    for h in body.holdings:
        sym = h.symbol.upper()
        sleeve = resolve_bucket(h.bucket.value if hasattr(h.bucket, "value") else str(h.bucket))
        if sleeve == "medium":
            sleeve = DEFAULT_BUCKET
            notes.append(f"{sym}: medium bucket mapped to penny for decisions")
        price = _last_price(ps, sym) or float(h.avg_cost)
        mv = price * float(h.shares)
        priced.append(
            {
                "symbol": sym,
                "shares": float(h.shares),
                "avg_cost": float(h.avg_cost),
                "bucket": sleeve,
                "price": price,
                "market_value": mv,
            }
        )

    total_value = cash + sum(p["market_value"] for p in priced)
    if total_value <= 0:
        raise ValueError("Portfolio value must be positive")

    items: list[PortfolioDecisionItem] = []
    for row in priced:
        sym = row["symbol"]
        sleeve = row["bucket"]
        current_w = row["market_value"] / total_value

        try:
            ctx = _score_context(sym, sleeve)
        except Exception as exc:
            logger.warning("Decision context failed for %s: %s", sym, exc)
            ctx = {"score": 50.0, "risk_index": 50.0, "target_weight": SLEEVE_MAX_WEIGHT.get(sleeve, 0.05), "risk_flags": ["score_fetch_failed"], "dq": None}

        if ctx.get("error"):
            notes.append(f"{sym}: {ctx['error']}")

        score = ctx["score"]
        risk_index = ctx["risk_index"]
        target_w = min(float(ctx["target_weight"]), float(SLEEVE_MAX_WEIGHT.get(sleeve, 0.08)))
        decision, reasons = _decide(
            sleeve=sleeve,
            score=score,
            risk_index=risk_index,
            current_weight=current_w,
            target_weight=target_w,
            dq=ctx.get("dq"),
        )
        buy_pct, keep_pct, sell_pct = _action_pcts(decision)
        delta_w = target_w - current_w
        suggested_usd = round(delta_w * total_value, 2)

        if decision == "sell":
            suggested_usd = round(-row["market_value"], 2)
        elif decision == "trim":
            trim_to = target_w * 0.9
            suggested_usd = round((trim_to - current_w) * total_value, 2)

        items.append(
            PortfolioDecisionItem(
                symbol=sym,
                bucket=sleeve,
                price=round(row["price"], 4),
                shares=row["shares"],
                avg_cost=row["avg_cost"],
                market_value=round(row["market_value"], 2),
                current_weight=round(current_w * 100, 2),
                target_weight=round(target_w * 100, 2),
                buy_pct=buy_pct,
                keep_pct=keep_pct,
                sell_pct=sell_pct,
                decision=decision,
                score=round(score, 1),
                risk_index=round(risk_index, 1),
                suggested_dollar_action=suggested_usd,
                reasons=reasons,
                risk_flags=list(ctx.get("risk_flags") or []),
            )
        )

    as_of = _utcnow().isoformat()
    response = PortfolioDecisionResponse(
        as_of=as_of,
        cash=cash,
        total_value=round(total_value, 2),
        items=items,
        notes=notes + [
            "Model/rule-based research output — not financial advice.",
            "Penny positions use stricter trim/sell triggers than compounder.",
        ],
    )

    if body.persist:
        try:
            HistoricalStore().log_job(
                "portfolio_daily_decision",
                "ok",
                f"{len(items)} holdings",
                symbols_processed=len(items),
                errors=0,
                started_at=_utcnow(),
                finished_at=_utcnow(),
            )
        except Exception as exc:
            logger.debug("Decision snapshot log skipped: %s", exc)

    return response


def run_stored_portfolio_decision(*, trigger: str = "manual", persist: bool = True) -> PortfolioDecisionResponse:
    """Run daily decision from persisted holdings (CSV / manual / sync)."""
    from services.portfolio_snapshot_service import holdings_to_request

    cash, holdings = holdings_to_request()
    if not holdings:
        raise ValueError("No holdings on file — import Robinhood CSV or add positions first")

    body = PortfolioDecisionRequest(cash=cash, holdings=holdings, persist=False)
    response = run_portfolio_daily_decision(body)

    if persist:
        payload = response.model_dump()
        payload["trigger"] = trigger
        save_decision_snapshot(DEFAULT_ACCOUNT_ID, trigger, payload)

    return response
