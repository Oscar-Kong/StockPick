"""Phase 3 sleeve signal builders — expanded factor set."""
from __future__ import annotations

from config import OPENBB_ON_SCAN
from scoring.compounder_v3 import compounder_expanded_scores
from scoring.penny_factors import penny_expanded_scores
from screeners.base import CandidateContext, WeightedSignal
from services.openbb_integration import append_governance_signal
from engines.factor.catalog_v3 import FACTOR_CATALOG_V3


def build_penny_signals_v3(ctx: CandidateContext) -> list[WeightedSignal]:
    df = ctx.history
    scores = penny_expanded_scores(ctx.symbol, df, ctx.info, ctx.fundamentals)
    mapping = [
        ("rel_volume", "Relative volume"),
        ("volume_surge", "Volume surge"),
        ("breakout_strength", "Breakout strength"),
        ("social_sentiment", "Social sentiment"),
        ("sentiment_pos", "Sentiment positive"),
        ("sentiment_neg", "Sentiment negative"),
        ("intraday_vol", "Intraday volatility"),
        ("float_size", "Float size"),
    ]
    specs = {s.factor_id.split("_", 1)[1]: s for s in FACTOR_CATALOG_V3["penny"]}
    return [
        WeightedSignal(
            label,
            scores.get(key, 50.0),
            specs[key].weight,
            f"Penny factor {key}",
        )
        for key, label in mapping
    ]


def build_compounder_signals_v3(ctx: CandidateContext) -> list[WeightedSignal]:
    df = ctx.history
    scores = compounder_expanded_scores(df, ctx.info, ctx.fundamentals)
    specs = {s.factor_id.split("_", 1)[1]: s for s in FACTOR_CATALOG_V3["compounder"]}
    signals = [
        WeightedSignal("Revenue growth", scores["rev_growth"], specs["rev_growth"].weight, "YoY revenue growth"),
        WeightedSignal("EPS growth (adjusted)", scores["adjusted_eps"], specs["eps_growth"].weight, "Adjusted EPS quality"),
        WeightedSignal("ROIC quality", scores["roic"], specs["roic"].weight, "ROIC and margins"),
        WeightedSignal("FCF yield", scores["fcf_yield"], specs["fcf_yield"].weight, "Free cash flow / market cap"),
        WeightedSignal("Debt ratio", scores["debt_ratio"], specs["debt_ratio"].weight, "Leverage inverted score"),
        WeightedSignal("Goodwill ratio", scores["goodwill_ratio"], specs["goodwill_ratio"].weight, "Goodwill / assets"),
        WeightedSignal("Margin quality", scores["gross_operating_margin"], specs["gross_operating_margin"].weight, "Gross + operating margins"),
        WeightedSignal("Dividend growth", scores["dividend_growth"], specs["dividend_growth"].weight, "Dividend sustainability proxy"),
        WeightedSignal("PE percentile", scores["pe_pct_5y"], specs["pe_pct_5y"].weight, "PE vs fair band"),
        WeightedSignal("PB percentile", scores["pb_pct_5y"], specs["pb_pct_5y"].weight, "PB vs fair band"),
        WeightedSignal("PS percentile", scores["ps_pct_5y"], specs["ps_pct_5y"].weight, "PS vs fair band"),
    ]
    return append_governance_signal(signals, ctx.symbol, allow_fetch=OPENBB_ON_SCAN)
