"""Versioned staging data policies (Phase 9B)."""
from __future__ import annotations

from dataclasses import dataclass

HISTORICAL_ADJUSTED_PRICES_POLICY_ID = "historical_adjusted_prices_v1"
UNIVERSE_PIT_MEMBERSHIP_POLICY_ID = "universe_pit_membership_v1"
STAGING_READINESS_POLICY_ID = "factor_discovery_staging_readiness_v1"
STAGING_AUDIT_ARTIFACT_SCHEMA = "factor_discovery_staging_audit_v1"


@dataclass(frozen=True)
class HistoricalAdjustedPricesPolicy:
    policy_id: str = HISTORICAL_ADJUSTED_PRICES_POLICY_ID
    provider_id: str = "historical_store_v1"
    adjustment_semantics: str = "provider_declared_split_dividend_adjusted_close"
    supported_exchanges: tuple[str, ...] = ("NYSE", "NASDAQ", "AMEX")
    currency_policy: str = "USD"
    timezone_policy: str = "America/New_York"
    session_calendar_policy: str = "us_equity_regular_v1"
    duplicate_policy: str = "reject_conflicting"
    missing_session_policy: str = "report_not_impute"
    split_policy: str = "provider_adjusted_close"
    dividend_policy: str = "provider_adjusted_close"
    delisting_limitation: str = "missing_horizon_end_prices_remain_missing"

    def to_dict(self) -> dict:
        return {
            "policy_id": self.policy_id,
            "provider_id": self.provider_id,
            "adjustment_semantics": self.adjustment_semantics,
            "supported_exchanges": list(self.supported_exchanges),
            "currency_policy": self.currency_policy,
            "timezone_policy": self.timezone_policy,
            "session_calendar_policy": self.session_calendar_policy,
            "duplicate_policy": self.duplicate_policy,
            "missing_session_policy": self.missing_session_policy,
            "split_policy": self.split_policy,
            "dividend_policy": self.dividend_policy,
            "delisting_limitation": self.delisting_limitation,
        }


@dataclass(frozen=True)
class UniversePitMembershipPolicy:
    policy_id: str = UNIVERSE_PIT_MEMBERSHIP_POLICY_ID
    universe_source_id: str = "staging_universe_v1"
    eligibility_meaning: str = "historical_listing_eligibility_at_score_date"
    effective_date_convention: str = "inclusive_start"
    exit_date_convention: str = "inclusive_end"
    delisted_symbol_treatment: str = "membership_ends_on_exit_date"
    missing_membership_behavior: str = "not_eligible"

    def to_dict(self) -> dict:
        return {
            "policy_id": self.policy_id,
            "universe_source_id": self.universe_source_id,
            "eligibility_meaning": self.eligibility_meaning,
            "effective_date_convention": self.effective_date_convention,
            "exit_date_convention": self.exit_date_convention,
            "delisted_symbol_treatment": self.delisted_symbol_treatment,
            "missing_membership_behavior": self.missing_membership_behavior,
        }


STAGING_FROZEN_FACTOR = {
    "factor_key": "staging_return_126d_rank",
    "display_name": "Staging Return 126D Rank",
    "dsl": "rank(return_126d)",
    "direction": "long_high",
    "family_suffix": "staging_price_only_v1",
    "actor": "staging-operator",
    "reason": "Phase 9B.1 frozen price-only reproducibility factor",
}

STAGING_FACTOR_DEFINITIONS = (
    {
        "factor_key": "staging_momentum_20d",
        "display_name": "Staging Momentum 20D",
        "dsl": "rank(delta(adjusted_close, 20))",
        "direction": "long_high",
        "family_suffix": "staging_price_only_v1",
    },
    {
        "factor_key": "staging_reversal_5d",
        "display_name": "Staging Reversal 5D",
        "dsl": "rank(negate(delta(adjusted_close, 5)))",
        "direction": "long_high",
        "family_suffix": "staging_price_only_v1",
    },
    {
        "factor_key": "staging_relative_volume",
        "display_name": "Staging Relative Volume",
        "dsl": "rank(relative_volume)",
        "direction": "long_high",
        "family_suffix": "staging_price_only_v1",
    },
)

STAGING_VALIDATION_CONFIG = {
    "config_id": "staging_validation_config_v1",
    "discovery_start": "2020-01-02",
    "discovery_end": "2021-12-31",
    "validation_start": "2022-01-03",
    "validation_end": "2022-12-30",
    "sealed_test_start": "2023-01-03",
    "sealed_test_end": "2023-06-30",
    "primary_horizon": 20,
    "outcome_horizons": [5, 20, 60],
    "transaction_cost_bps": 10,
    "rebalance": "monthly",
    "embargo_sessions": 0,
    "min_sealed_test_days": 60,
    "sealed_access": False,
}

STAGING_COVERAGE_MINIMUMS = {
    "min_eligible_symbols_per_date": 3,
    "min_valid_validation_dates": 20,
    "min_score_coverage_ratio": 0.5,
    "max_missing_outcome_rate": 0.25,
    "min_walk_forward_folds": 2,
}
