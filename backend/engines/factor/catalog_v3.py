"""Phase 3 factor catalog — expanded sleeves per INSTITUTIONAL_QUANT_ARCHITECTURE §5."""
from __future__ import annotations

from engines.factor.catalog import FactorSpec, _fid

FACTOR_CATALOG_V3: dict[str, list[FactorSpec]] = {
    "penny": [
        FactorSpec(_fid("penny", "rel_volume"), "Relative volume", 0.22, "critical", signal_name="Relative volume"),
        FactorSpec(_fid("penny", "volume_surge"), "Volume surge", 0.22, "critical", signal_name="Volume surge"),
        FactorSpec(_fid("penny", "breakout_strength"), "Breakout strength", 0.16, "important", signal_name="Breakout strength"),
        FactorSpec(_fid("penny", "social_sentiment"), "Social sentiment", 0.16, "important", signal_name="Social sentiment"),
        FactorSpec(_fid("penny", "sentiment_pos"), "Sentiment positive", 0.08, "secondary", signal_name="Sentiment positive"),
        FactorSpec(_fid("penny", "sentiment_neg"), "Sentiment negative", 0.04, "secondary", signal_name="Sentiment negative"),
        FactorSpec(_fid("penny", "intraday_vol"), "Intraday volatility", 0.08, "secondary", signal_name="Intraday volatility"),
        FactorSpec(_fid("penny", "float_size"), "Float size", 0.04, "secondary", signal_name="Float size"),
    ],
    "compounder": [
        FactorSpec(_fid("compounder", "rev_growth"), "Revenue growth", 0.15, "critical", signal_name="Revenue growth"),
        FactorSpec(_fid("compounder", "eps_growth"), "EPS growth (adjusted)", 0.13, "critical", signal_name="EPS growth (adjusted)"),
        FactorSpec(_fid("compounder", "roic"), "ROIC quality", 0.15, "critical", signal_name="ROIC quality"),
        FactorSpec(_fid("compounder", "fcf_yield"), "FCF yield", 0.12, "important", signal_name="FCF yield"),
        FactorSpec(_fid("compounder", "debt_ratio"), "Debt ratio", 0.08, "important", signal_name="Debt ratio"),
        FactorSpec(_fid("compounder", "goodwill_ratio"), "Goodwill ratio", 0.04, "secondary", signal_name="Goodwill ratio"),
        FactorSpec(_fid("compounder", "gross_operating_margin"), "Margin quality", 0.10, "important", signal_name="Margin quality"),
        FactorSpec(_fid("compounder", "dividend_growth"), "Dividend growth", 0.08, "secondary", signal_name="Dividend growth"),
        FactorSpec(_fid("compounder", "pe_pct_5y"), "PE percentile", 0.05, "secondary", signal_name="PE percentile"),
        FactorSpec(_fid("compounder", "pb_pct_5y"), "PB percentile", 0.05, "secondary", signal_name="PB percentile"),
        FactorSpec(_fid("compounder", "ps_pct_5y"), "PS percentile", 0.05, "secondary", signal_name="PS percentile"),
    ],
}
