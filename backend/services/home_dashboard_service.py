"""Build home daily decision dashboard payload."""
from __future__ import annotations

from models.schemas import Bucket, DailyDashboardResponse, PennyOpportunityItem, PortfolioDecisionResponse
from data.portfolio_store import get_latest_decision
from services.portfolio_snapshot_service import DISCLAIMER, get_current_portfolio
from services.scan_manager import scan_manager


_SOURCE_LABELS = {
    "manual": "Manual holdings",
    "csv": "CSV imported",
    "snaptrade": "Robinhood synced (SnapTrade)",
}


def _top_penny_opportunities(limit: int = 5) -> list[PennyOpportunityItem]:
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


def _portfolio_warnings(portfolio: dict, decision: PortfolioDecisionResponse | None) -> list[str]:
    warnings: list[str] = []
    if not portfolio.get("holdings"):
        warnings.append("No holdings loaded — import Robinhood CSV to get started")
    if portfolio.get("data_source") == "manual" and not portfolio.get("holdings"):
        warnings.append("Data source: manual — upload CSV for trade history reconstruction")
    if decision:
        sells = [i for i in decision.items if i.decision in ("sell", "trim")]
        if len(sells) >= 3:
            warnings.append(f"{len(sells)} positions flagged trim/sell — review risk before acting")
    return warnings


def build_daily_dashboard() -> DailyDashboardResponse:
    portfolio = get_current_portfolio()
    latest = get_latest_decision()

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
    holdings = portfolio.get("holdings") or []
    total_value = decision.total_value if decision else sum(h.get("shares", 0) * h.get("avg_cost", 0) for h in holdings) + cash

    return DailyDashboardResponse(
        portfolio_value=round(total_value, 2),
        cash=cash,
        data_source=source,
        data_source_label=_SOURCE_LABELS.get(source, source.title()),
        last_brokerage_sync_at=account.get("last_sync_at"),
        last_decision_run_at=last_run,
        decision=decision,
        holdings=holdings,
        top_penny_opportunities=_top_penny_opportunities(),
        portfolio_warnings=_portfolio_warnings(portfolio, decision),
        disclaimer=DISCLAIMER,
    )
