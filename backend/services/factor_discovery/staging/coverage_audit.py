"""Coverage audit for staging factor runs."""
from __future__ import annotations

from dataclasses import dataclass, field

from engines.factor.discovery.panel_models import FactorInputPanel
from services.factor_discovery.staging.policies import STAGING_COVERAGE_MINIMUMS


@dataclass
class CoverageAuditReport:
    required_fields: list[str] = field(default_factory=list)
    available_fields: list[str] = field(default_factory=list)
    score_coverage_ratio: float = 0.0
    eligible_symbol_coverage: float = 0.0
    valid_cross_sectional_dates: int = 0
    missing_horizon_end_rate: float = 0.0
    blocking_codes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "required_fields": self.required_fields,
            "available_fields": self.available_fields,
            "score_coverage_ratio": self.score_coverage_ratio,
            "eligible_symbol_coverage": self.eligible_symbol_coverage,
            "valid_cross_sectional_dates": self.valid_cross_sectional_dates,
            "missing_horizon_end_rate": self.missing_horizon_end_rate,
            "blocking_codes": self.blocking_codes,
            "minimums": STAGING_COVERAGE_MINIMUMS,
        }


class FactorDiscoveryCoverageAuditService:
    def audit_panel(
        self,
        panel: FactorInputPanel,
        *,
        required_fields: set[str],
        missing_outcome_rate: float = 0.0,
    ) -> CoverageAuditReport:
        report = CoverageAuditReport(
            required_fields=sorted(required_fields),
            available_fields=sorted(panel.frame.columns.tolist()),
            missing_horizon_end_rate=missing_outcome_rate,
        )
        missing = required_fields - set(panel.frame.columns)
        if missing:
            report.blocking_codes.append(f"missing_primitive_fields:{','.join(sorted(missing))}")
        eligible = panel.eligibility.astype(bool)
        report.score_coverage_ratio = float(eligible.mean()) if len(eligible) else 0.0
        by_date = eligible.groupby(level=0).mean()
        report.valid_cross_sectional_dates = int((by_date >= STAGING_COVERAGE_MINIMUMS["min_score_coverage_ratio"]).sum())
        min_sym = STAGING_COVERAGE_MINIMUMS["min_eligible_symbols_per_date"]
        sym_counts = eligible.groupby(level=0).sum()
        if sym_counts.min() < min_sym:
            report.blocking_codes.append("insufficient_eligible_symbols_per_date")
        if report.valid_cross_sectional_dates < STAGING_COVERAGE_MINIMUMS["min_valid_validation_dates"]:
            report.blocking_codes.append("insufficient_valid_cross_sectional_dates")
        if missing_outcome_rate > STAGING_COVERAGE_MINIMUMS["max_missing_outcome_rate"]:
            report.blocking_codes.append("missing_outcome_rate_exceeds_threshold")
        return report
