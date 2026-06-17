"""Build home daily decision dashboard payload."""
from __future__ import annotations

from models.schemas import (
    Bucket,
    ClosedPositionItem,
    DailyDashboardResponse,
    PennyOpportunityItem,
    PortfolioDecisionResponse,
)
from data.portfolio_store import get_latest_decision, get_latest_portfolio_snapshot, list_uploads, load_all_ledger_rows
from integrations.robinhood.portfolio_rebuilder import rebuild_portfolio
from services.data_freshness_service import assess_all_freshness, assess_freshness
from services.portfolio_snapshot_service import DISCLAIMER, estimate_ledger_cash, get_current_portfolio
from services.refresh_orchestrator import get_active_home_job_id, is_home_refresh_running
from services.scan_manager import scan_manager

_SOURCE_LABELS = {
    "manual": "Manual holdings",
    "csv": "Robinhood CSV",
    "snaptrade": "Robinhood (SnapTrade)",
    "demo": "Demo / mock data",
}


def _top_penny_opportunities(*, cash: float, allow_new_buys: bool, limit: int = 5) -> list[PennyOpportunityItem]:
    if not allow_new_buys or cash < 50:
        return []
    data = scan_manager.get_latest_scan(Bucket.penny)
    if not data:
        return []
    results = data.get("results") or []
    out: list[PennyOpportunityItem] = []
    for r in results[:limit]:
        metrics = r.get("metrics") or {}
        out.append(
            PennyOpportunityItem(
                symbol=r.get("symbol", ""),
                score=float(r.get("score") or 0),
                price=float(r.get("price") or 0),
                setup_type=metrics.get("setup_type"),
                summary=str(r.get("summary") or "")[:160],
            )
        )
    return out


def _risk_alerts(decision: PortfolioDecisionResponse | None, portfolio: dict) -> list[str]:
    alerts: list[str] = []
    if not portfolio.get("holdings"):
        alerts.append("No active holdings — import Robinhood CSV to reconstruct positions")
    if portfolio.get("is_demo_data"):
        alerts.append("Demo/mock data source — not your real Robinhood portfolio")
    if not decision:
        return alerts
    for item in decision.items:
        if item.price_available is False:
            alerts.append(f"{item.symbol}: missing latest price — decision is REVIEW")
        if bool(item.stop_loss_trigger):
            alerts.append(f"{item.symbol}: drawdown stop triggered — review exit")
        ow_penalty = float(item.overweight_penalty or 0)
        if "overweight" in (item.risk_flags or []) or ow_penalty > 0:
            alerts.append(f"{item.symbol}: position overweight vs penny/compounder cap")
        if item.decision == "sell":
            action = item.suggested_action or "review position"
            alerts.append(f"{item.symbol}: SELL/trim signal — {action}")
        risk = float(item.risk_score if item.risk_score is not None else item.risk_index or 0)
        if item.bucket == "penny" and risk >= 70:
            alerts.append(f"{item.symbol}: high-risk penny name")
    return list(dict.fromkeys(alerts))[:20]


def _portfolio_warnings(portfolio: dict, decision: PortfolioDecisionResponse | None) -> list[str]:
    warnings: list[str] = []
    source = portfolio.get("data_source") or "manual"
    if source == "demo":
        warnings.append("⚠ Demo data — do not treat as real Robinhood holdings")
    elif source == "manual" and not portfolio.get("holdings"):
        warnings.append("Upload Robinhood CSV to reconstruct holdings from trade history")
    if decision:
        reviews = [i for i in decision.items if i.decision == "review"]
        if reviews:
            warnings.append(f"{len(reviews)} positions need REVIEW due to missing or weak data")
    return warnings


def build_daily_dashboard(*, include_freshness: bool = False) -> DailyDashboardResponse:
    portfolio = get_current_portfolio()
    latest = get_latest_decision()
    snap = get_latest_portfolio_snapshot()

    decision: PortfolioDecisionResponse | None = None
    last_run: str | None = None
    if latest:
        last_run = latest.get("created_at")
        payload = latest.get("payload") or {}
        if payload.get("items") is not None:
            decision = PortfolioDecisionResponse(**payload)

    account = portfolio.get("account") or {}
    source = portfolio.get("data_source") or account.get("source") or "manual"
    cash = float(portfolio.get("cash") or 0)
    reserved_cash = float(portfolio.get("reserved_cash") or 0)
    holdings = portfolio.get("holdings") or []
    closed_raw = portfolio.get("closed_positions") or []
    closed = [ClosedPositionItem(**c) if isinstance(c, dict) else c for c in closed_raw]

    if decision:
        by_sym = {i.symbol: i for i in decision.items}
        invested = 0.0
        for h in holdings:
            item = by_sym.get(h["symbol"])
            if item and item.price_available and (item.market_value or 0) > 0:
                invested += float(item.market_value)
            else:
                invested += float(h.get("shares", 0)) * float(h.get("avg_cost", 0))
        if not holdings and decision.invested_value is not None:
            invested = float(decision.invested_value or 0)
        elif not decision.items and decision.invested_value is not None and invested <= 0:
            invested = float(decision.invested_value)
    elif holdings:
        invested = sum(h.get("shares", 0) * h.get("avg_cost", 0) for h in holdings)
    else:
        invested = max(0.0, float((snap or {}).get("total_value") or 0) - cash)

    # Robinhood: total = buying power + reserved (IPO) + invested holdings.
    total_value = cash + reserved_cash + invested

    cash_pct = round(cash / total_value * 100, 2) if total_value > 0 else 0.0
    allow_buys = source in ("csv", "snaptrade") and bool(holdings) and source != "demo"

    warnings = _portfolio_warnings(portfolio, decision)
    decision_stale_warning: str | None = None
    if include_freshness:
        d_status = assess_freshness("daily_decision")
        if d_status.is_stale or d_status.is_missing:
            decision_stale_warning = "Decision is based on older data. Refresh before acting."
            warnings = list(dict.fromkeys(warnings + [decision_stale_warning]))
        if portfolio.get("is_demo_data"):
            demo_msg = "Demo data is displayed. Import Robinhood CSV before making decisions."
            warnings = list(dict.fromkeys([demo_msg] + warnings))

    freshness = None
    if include_freshness:
        in_progress = is_home_refresh_running()
        active_job = get_active_home_job_id() if in_progress else None
        freshness = assess_all_freshness(refresh_in_progress=in_progress, refresh_job_id=active_job)
        if freshness.overall_status == "demo":
            pass
        elif portfolio.get("is_demo_data"):
            freshness.overall_status = "demo"

    csv_rows_loaded: int | None = None
    ledger_rows_count: int | None = None
    ledger_cash_estimate: float | None = None
    cash_source: str | None = portfolio.get("cash_source")
    if source == "csv":
        uploads = list_uploads()
        if uploads:
            csv_rows_loaded = int(uploads[0].get("row_count") or 0)
        ledger_rows = load_all_ledger_rows()
        ledger_rows_count = len(ledger_rows)
        ledger_cash_estimate = round(estimate_ledger_cash(), 2)

    return DailyDashboardResponse(
        portfolio_value=round(total_value, 2),
        cash=cash,
        reserved_cash=reserved_cash,
        ipo_shares=portfolio.get("ipo_shares"),
        ipo_list_price=portfolio.get("ipo_list_price"),
        ipo_buffer=1.2,
        invested_value=round(invested, 2),
        cash_pct=cash_pct,
        active_holdings_count=len(holdings),
        data_source=source,
        data_source_label=_SOURCE_LABELS.get(source, source.title()),
        is_demo_data=bool(portfolio.get("is_demo_data")),
        last_brokerage_sync_at=account.get("last_sync_at"),
        last_decision_run_at=last_run,
        decision=decision,
        holdings=holdings,
        closed_positions=closed,
        top_penny_opportunities=_top_penny_opportunities(cash=cash, allow_new_buys=allow_buys),
        risk_alerts=_risk_alerts(decision, portfolio),
        portfolio_warnings=warnings,
        disclaimer=DISCLAIMER,
        freshness=freshness,
        decision_stale_warning=decision_stale_warning,
        csv_rows_loaded=csv_rows_loaded,
        ledger_rows_count=ledger_rows_count,
        ledger_cash_estimate=ledger_cash_estimate,
        cash_source=cash_source,
    )
