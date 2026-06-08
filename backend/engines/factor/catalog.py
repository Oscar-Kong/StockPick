"""Factor metadata catalog — static weights until Phase 2 dynamic weights."""
from __future__ import annotations

from dataclasses import dataclass

from config import SLEEVE_FACTORS_V3_ENABLED


@dataclass(frozen=True)
class FactorSpec:
    factor_id: str
    display_name: str
    weight: float
    tier: str = "important"
    formula_version: str = "2026-06-v1"
    signal_name: str = ""  # matches WeightedSignal.name in screeners


def _fid(sleeve: str, key: str) -> str:
    return f"{sleeve}_{key}"


FACTOR_CATALOG: dict[str, list[FactorSpec]] = {
    "penny": [
        FactorSpec(_fid("penny", "momentum_5d"), "5-day momentum", 0.25, "critical", signal_name="5-day momentum"),
        FactorSpec(_fid("penny", "volume_spike"), "Volume spike", 0.25, "critical", signal_name="Volume spike"),
        FactorSpec(_fid("penny", "rsi_fit"), "RSI fit", 0.15, "important", signal_name="RSI fit"),
        FactorSpec(_fid("penny", "social_buzz"), "Social buzz", 0.20, "important", signal_name="Social buzz"),
        FactorSpec(_fid("penny", "volatility_fit"), "Volatility fit", 0.15, "secondary", signal_name="Volatility fit"),
    ],
    "medium": [
        # Nominal weights when governance leg is active (base × 0.95 + 5% gov)
        FactorSpec(_fid("medium", "rs_vs_spy"), "20d momentum vs SPY", 0.209, "critical", signal_name="20d momentum vs SPY"),
        FactorSpec(_fid("medium", "technical_setup"), "Technical setup", 0.2185, "critical", signal_name="Technical setup"),
        FactorSpec(_fid("medium", "sector_rs"), "Sector RS vs SPY", 0.171, "important", signal_name="Sector RS vs SPY"),
        FactorSpec(_fid("medium", "qlib_alpha"), "Qlib alpha (20d)", 0.171, "important", signal_name="Qlib alpha (20d)"),
        FactorSpec(_fid("medium", "sentiment"), "Sentiment", 0.1805, "important", signal_name="Sentiment"),
        FactorSpec(
            _fid("medium", "governance"),
            "SEC / insider governance",
            0.05,
            "secondary",
            signal_name="SEC / insider governance",
        ),
    ],
    "compounder": [
        FactorSpec(
            _fid("compounder", "rev_eps"),
            "Revenue/EPS consistency",
            0.266,
            "critical",
            signal_name="Revenue/EPS consistency",
        ),
        FactorSpec(_fid("compounder", "roic_margins"), "ROIC & margins", 0.228, "critical", signal_name="ROIC & margins"),
        FactorSpec(_fid("compounder", "smooth_growth"), "5Y smooth growth", 0.19, "important", signal_name="5Y smooth growth"),
        FactorSpec(_fid("compounder", "moat"), "Moat proxies", 0.1235, "important", signal_name="Moat proxies"),
        FactorSpec(_fid("compounder", "macro_regime"), "Macro regime", 0.095, "secondary", signal_name="Macro regime"),
        FactorSpec(_fid("compounder", "qlib_alpha"), "Qlib alpha", 0.0475, "secondary", signal_name="Qlib alpha"),
        FactorSpec(
            _fid("compounder", "governance"),
            "SEC / insider governance",
            0.05,
            "secondary",
            signal_name="SEC / insider governance",
        ),
    ],
}


def active_factor_catalog() -> dict[str, list[FactorSpec]]:
    if SLEEVE_FACTORS_V3_ENABLED:
        from engines.factor.catalog_v3 import FACTOR_CATALOG_V3

        base = FACTOR_CATALOG_V3
    else:
        base = FACTOR_CATALOG
    from config import OPENALPHA_FACTORS_ENABLED

    if OPENALPHA_FACTORS_ENABLED:
        from engines.factor.openalpha_catalog import merge_catalog_with_openalpha

        return merge_catalog_with_openalpha(base)
    return base


def static_weights(sleeve: str) -> dict[str, float]:
    """Catalog default weights keyed by factor_id."""
    return {spec.factor_id: spec.weight for spec in active_factor_catalog().get(sleeve, [])}


def factor_id_to_signal_name(sleeve: str, factor_id: str) -> str | None:
    for spec in active_factor_catalog().get(sleeve, []):
        if spec.factor_id == factor_id:
            return spec.signal_name or spec.display_name
    return None


def signal_name_to_factor_id(sleeve: str, signal_name: str) -> str:
    for spec in active_factor_catalog().get(sleeve, []):
        if spec.signal_name == signal_name or spec.display_name == signal_name:
            return spec.factor_id
    slug = signal_name.lower().replace(" ", "_").replace("/", "_").replace("(", "").replace(")", "")
    slug = "".join(c if c.isalnum() or c == "_" else "_" for c in slug)
    while "__" in slug:
        slug = slug.replace("__", "_")
    return f"{sleeve}_{slug.strip('_')[:48]}"
