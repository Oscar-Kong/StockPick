"""Regime-specific weight multipliers per factor (sleeve × regime)."""
from __future__ import annotations

# factor_id → multiplier; omitted factors default to 1.0

MEDIUM_OVERLAYS: dict[str, dict[str, float]] = {
    "bull": {
        "medium_rs_vs_spy": 1.25,
        "medium_technical_setup": 1.15,
        "medium_sector_rs": 1.20,
        "medium_sentiment": 1.10,
        "medium_governance": 0.90,
    },
    "bear": {
        "medium_rs_vs_spy": 0.70,
        "medium_technical_setup": 0.90,
        "medium_sector_rs": 0.80,
        "medium_sentiment": 1.00,
        "medium_governance": 1.20,
    },
    "sideways": {
        "medium_technical_setup": 1.05,
        "medium_sentiment": 0.95,
        "medium_governance": 1.10,
    },
    "high_vol": {
        "medium_rs_vs_spy": 0.85,
        "medium_technical_setup": 0.95,
        "medium_sector_rs": 0.90,
        "medium_sentiment": 1.15,
        "medium_governance": 1.10,
    },
    "low_vol": {
        "medium_rs_vs_spy": 1.10,
        "medium_sector_rs": 1.05,
        "medium_sentiment": 0.90,
    },
    "neutral": {},
}

PENNY_OVERLAYS: dict[str, dict[str, float]] = {
    "bull": {
        "penny_volume_spike": 1.20,
        "penny_social_buzz": 1.15,
        "penny_momentum_5d": 1.10,
    },
    "bear": {
        "penny_volume_spike": 0.85,
        "penny_social_buzz": 0.90,
        "penny_momentum_5d": 0.80,
        "penny_volatility_fit": 1.10,
    },
    "sideways": {
        "penny_volume_spike": 1.10,
        "penny_social_buzz": 1.10,
    },
    "high_vol": {
        "penny_volume_spike": 0.80,
        "penny_momentum_5d": 0.85,
        "penny_volatility_fit": 1.15,
    },
    "low_vol": {
        "penny_momentum_5d": 1.05,
        "penny_rsi_fit": 1.10,
    },
    "neutral": {},
}

COMPOUNDER_OVERLAYS: dict[str, dict[str, float]] = {
    "bull": {
        "compounder_smooth_growth": 1.10,
        "compounder_qlib_alpha": 1.15,
    },
    "bear": {
        "compounder_rev_eps": 1.15,
        "compounder_roic_margins": 1.15,
        "compounder_moat": 1.20,
        "compounder_macro_regime": 1.10,
    },
    "low_vol": {
        "compounder_rev_eps": 1.10,
        "compounder_moat": 1.15,
        "compounder_roic_margins": 1.10,
    },
    "high_vol": {
        "compounder_smooth_growth": 0.90,
        "compounder_qlib_alpha": 0.85,
    },
    "sideways": {
        "compounder_macro_regime": 1.05,
    },
    "neutral": {},
}

SLEEVE_OVERLAYS: dict[str, dict[str, dict[str, float]]] = {
    "penny": PENNY_OVERLAYS,
    "medium": MEDIUM_OVERLAYS,
    "compounder": COMPOUNDER_OVERLAYS,
}


def overlay_multiplier(sleeve: str, regime: str, factor_id: str) -> float:
    table = SLEEVE_OVERLAYS.get(sleeve, {})
    return float(table.get(regime, {}).get(factor_id, 1.0))
