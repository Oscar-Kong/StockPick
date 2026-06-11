"""Daily portfolio decision support — rule engine with explainability."""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from buckets import DEFAULT_BUCKET, resolve_bucket
from config import SLEEVE_MAX_WEIGHT
from data.historical_store import HistoricalStore
from data.portfolio_store import DEFAULT_ACCOUNT_ID, save_decision_snapshot
from data.price_service import PriceService
from data.reconciler import DataReconciler
from models.schemas import (
    ClosedPositionItem,
    PortfolioDecisionItem,
    PortfolioDecisionRequest,
    PortfolioDecisionResponse,
)
from services.portfolio_decision_engine import DecisionInput, compute_holding_decision, max_weight_for_sleeve
from services.quant_risk_sizing_service import build_unified_risk, sizing_from_score_context
from services.quant_v2_service import build_v2_score
from services.data_freshness_service import is_symbol_price_stale
from utils.pydantic_util import model_to_dict

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _last_price(ps: PriceService, symbol: str) -> float | None:
    df = ps.get_history(symbol, period="5d")
    if df is None or df.empty:
        return None
    return float(df["close"].iloc[-1])


def _momentum_score(symbol: str, ps: PriceService) -> float:
    df = ps.get_history(symbol, period="3mo")
    if df is None or len(df) < 20:
        return 50.0
    close = df["close"]
    ret_20 = (close.iloc[-1] / close.iloc[-20] - 1) * 100 if len(close) >= 20 else 0
    ret_5 = (close.iloc[-1] / close.iloc[-5] - 1) * 100 if len(close) >= 5 else 0
    score = 50 + ret_20 * 1.2 + ret_5 * 0.8
    return max(0.0, min(100.0, score))


def _liquidity_score(symbol: str, ps: PriceService) -> float:
    df = ps.get_history(symbol, period="1mo")
    if df is None or df.empty:
        return 45.0
    vol = df.get("volume")
    if vol is None or vol.empty:
        return 50.0
    avg_vol = float(vol.tail(10).mean())
    if avg_vol >= 5_000_000:
        return 85.0
    if avg_vol >= 1_000_000:
        return 70.0
    if avg_vol >= 200_000:
        return 55.0
    if avg_vol >= 50_000:
        return 40.0
    return 25.0


def _score_context(symbol: str, sleeve: str, ps: PriceService) -> dict:
    score_res = build_v2_score(
        symbol,
        sleeve,
        validate_parity=False,
        include_sizing=False,
        persist_snapshot=False,
    )
    if isinstance(score_res, dict) and score_res.get("error"):
        return {
            "error": score_res.get("error"),
            "alpha": 50.0,
            "risk_index": 50.0,
            "momentum": _momentum_score(symbol, ps),
            "liquidity": _liquidity_score(symbol, ps),
        }

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
        "alpha": float(score_res.score),
        "risk_index": float(risk_index),
        "target_weight": float(target_w),
        "dq": dq,
        "risk_flags": risk_flags,
        "momentum": _momentum_score(symbol, ps),
        "liquidity": _liquidity_score(symbol, ps),
    }


def run_portfolio_daily_decision(body: PortfolioDecisionRequest) -> PortfolioDecisionResponse:
    ps = PriceService()
    cash = max(0.0, float(body.cash))
    reserved = max(0.0, float(body.reserved_cash))
    notes: list[str] = []

    priced: list[dict] = []
    for h in body.holdings:
        sym = h.symbol.upper()
        sleeve = resolve_bucket(h.bucket.value if hasattr(h.bucket, "value") else str(h.bucket))
        if sleeve == "medium":
            sleeve = DEFAULT_BUCKET
            notes.append(f"{sym}: medium bucket deprecated — using penny rules")
        latest = _last_price(ps, sym)
        price_for_mv = latest  # no avg_cost fallback for decisions
        mv = (price_for_mv * float(h.shares)) if price_for_mv else 0.0
        priced.append(
            {
                "symbol": sym,
                "shares": float(h.shares),
                "avg_cost": float(h.avg_cost),
                "bucket": sleeve,
                "latest_price": latest,
                "market_value": mv,
            }
        )

    invested = sum(p["market_value"] for p in priced if p["latest_price"])
    total_value = cash + reserved + invested
    if total_value <= 0 and not priced:
        raise ValueError("Portfolio value must be positive")

    # If all prices missing, use cost basis only for display total — decisions still REVIEW
    if total_value <= 0:
        total_value = cash + reserved + sum(p["avg_cost"] * p["shares"] for p in priced)

    def _item_for_row(row: dict) -> tuple[PortfolioDecisionItem, str | None]:
        sym = row["symbol"]
        sleeve = row["bucket"]
        latest = row["latest_price"]
        mv = row["market_value"] if latest else row["avg_cost"] * row["shares"]
        current_w = mv / total_value if total_value > 0 else 0.0
        note: str | None = None

        try:
            ctx = _score_context(sym, sleeve, ps)
        except Exception as exc:
            logger.warning("Decision context failed for %s: %s", sym, exc)
            ctx = {
                "alpha": 50.0,
                "risk_index": 50.0,
                "target_weight": SLEEVE_MAX_WEIGHT.get(sleeve, 0.05),
                "risk_flags": ["score_fetch_failed"],
                "dq": None,
                "momentum": 50.0,
                "liquidity": 45.0,
            }

        if ctx.get("error"):
            note = f"{sym}: {ctx['error']}"

        target_w = min(float(ctx["target_weight"]), max_weight_for_sleeve(sleeve))
        max_w = max_weight_for_sleeve(sleeve)

        out = compute_holding_decision(
            DecisionInput(
                symbol=sym,
                sleeve=sleeve,
                shares=row["shares"],
                avg_cost=row["avg_cost"],
                latest_price=latest,
                alpha_score=ctx["alpha"],
                momentum_score=ctx["momentum"],
                liquidity_score=ctx["liquidity"],
                risk_score=ctx["risk_index"],
                data_quality_score=ctx.get("dq"),
                current_weight=current_w,
                target_weight=target_w,
                max_allowed_weight=max_w,
                price_stale=is_symbol_price_stale(sym) if latest else False,
            ),
            total_portfolio_value=total_value,
        )

        pl_pct = None
        if latest and row["avg_cost"] > 0:
            pl_pct = round((latest - row["avg_cost"]) / row["avg_cost"] * 100, 2)

        flags = list(dict.fromkeys(list(ctx.get("risk_flags") or []) + out.risk_flags))

        item = PortfolioDecisionItem(
            symbol=sym,
            bucket=sleeve,
            price=round(latest, 4) if latest else 0.0,
            price_available=out.price_available,
            shares=row["shares"],
            avg_cost=row["avg_cost"],
            market_value=round(mv, 2),
            pl_pct=pl_pct,
            current_weight=round(current_w * 100, 2),
            target_weight=round(target_w * 100, 2),
            buy_pct=out.buy_pct,
            keep_pct=out.keep_pct,
            sell_pct=out.sell_pct,
            decision=out.final_decision,
            suggested_action=out.suggested_action,
            score=round(ctx["alpha"], 1),
            risk_index=round(ctx["risk_index"], 1),
            suggested_dollar_action=out.suggested_dollar_action,
            reasons=out.reasons,
            risk_flags=flags,
            alpha_score=out.alpha_score,
            momentum_score=out.momentum_score,
            liquidity_score=out.liquidity_score,
            risk_score=out.risk_score,
            data_quality_score=out.data_quality_score,
            max_allowed_weight=round(out.max_allowed_weight * 100, 2),
            overweight_penalty=round(out.overweight_penalty, 2),
            missing_data_penalty=round(out.missing_data_penalty, 2),
            stop_loss_trigger=out.stop_loss_trigger,
            final_buy_raw=out.final_buy_raw,
            final_keep_raw=out.final_keep_raw,
            final_sell_raw=out.final_sell_raw,
        )
        return item, note

    max_workers = min(6, max(1, len(priced)))
    if len(priced) <= 1:
        pairs = [_item_for_row(row) for row in priced]
    else:
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            pairs = list(pool.map(_item_for_row, priced))
    items = [p[0] for p in pairs]
    notes.extend(n for n in (p[1] for p in pairs) if n)

    as_of = _utcnow().isoformat()
    return PortfolioDecisionResponse(
        as_of=as_of,
        cash=cash,
        reserved_cash=reserved,
        total_value=round(total_value, 2),
        invested_value=round(invested, 2),
        items=items,
        notes=notes
        + [
            "Model-generated research output — not financial advice. The app does not place trades.",
            "Cost basis: weighted average cost from Robinhood CSV reconstruction.",
            "Penny positions use stricter add/trim rules than compounder.",
        ],
    )


def run_stored_portfolio_decision(*, trigger: str = "manual", persist: bool = True) -> PortfolioDecisionResponse:
    from services.portfolio_snapshot_service import holdings_to_request

    cash, reserved, holdings = holdings_to_request()
    if not holdings:
        raise ValueError("No holdings on file — import Robinhood CSV or add positions first")

    body = PortfolioDecisionRequest(cash=cash, reserved_cash=reserved, holdings=holdings, persist=False)
    response = run_portfolio_daily_decision(body)

    if persist:
        payload = model_to_dict(response)
        payload["trigger"] = trigger
        snap = save_decision_snapshot(DEFAULT_ACCOUNT_ID, trigger, payload)
        try:
            HistoricalStore().log_job(
                "portfolio_daily_decision",
                "ok",
                f"{len(response.items)} holdings",
                symbols_processed=len(response.items),
                errors=0,
                started_at=_utcnow(),
                finished_at=_utcnow(),
            )
        except Exception as exc:
            logger.debug("Decision job log skipped: %s", exc)
        payload["_snapshot_id"] = snap.get("id")

    return response


def closed_positions_from_snapshot() -> list[ClosedPositionItem]:
    from data.portfolio_store import get_latest_portfolio_snapshot

    snap = get_latest_portfolio_snapshot()
    if not snap:
        return []
    out: list[ClosedPositionItem] = []
    for c in snap.get("closed_positions") or []:
        if isinstance(c, dict):
            out.append(ClosedPositionItem(**c))
        else:
            out.append(
                ClosedPositionItem(
                    symbol=c.symbol,
                    total_bought=c.total_bought,
                    total_sold=c.total_sold,
                    realized_pl=c.realized_pl,
                    last_activity=getattr(c, "last_activity", ""),
                )
            )
    return out
