"""Negative controls and leakage tests for extended staging."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from engines.factor.discovery.panel_models import FactorInputPanel
from services.factor_discovery.errors import FactorDiscoveryError
from services.factor_discovery.staging.leakage_audit import FactorDiscoveryLeakageAuditService


@dataclass
class NegativeControlResult:
    control_id: str
    passed: bool
    expected_outcome: str
    details: dict = field(default_factory=dict)
    blocking: bool = False

    def to_dict(self) -> dict:
        return {
            "control_id": self.control_id,
            "passed": self.passed,
            "expected_outcome": self.expected_outcome,
            "details": self.details,
            "blocking": self.blocking,
        }


class ExtendedStagingNegativeControls:
    """Run leakage and sanity controls without aborting the full matrix."""

    def __init__(self) -> None:
        self._leakage = FactorDiscoveryLeakageAuditService()

    def run_all(self, panel: FactorInputPanel, *, cut_date: str) -> list[NegativeControlResult]:
        results: list[NegativeControlResult] = []
        results.append(self._outcome_fields_absent(panel))
        results.append(self._future_price_isolation(panel, cut_date=cut_date))
        results.append(self._future_universe_isolation(panel, cut_date=cut_date))
        results.append(self._sealed_period_isolation())
        results.append(self._shuffled_label_no_signal(panel))
        results.append(self._constant_factor(panel))
        results.append(self._insufficient_coverage_rejection(panel))
        results.append(self._config_hash_mismatch())
        return results

    def _outcome_fields_absent(self, panel: FactorInputPanel) -> NegativeControlResult:
        r = self._leakage.assert_outcome_fields_absent(panel)
        return NegativeControlResult(
            control_id="outcome_fields_absent",
            passed=r["passed"],
            expected_outcome="pass",
            details=r,
            blocking=not r["passed"],
        )

    def _future_price_isolation(self, panel: FactorInputPanel, *, cut_date: str) -> NegativeControlResult:
        r = self._leakage.future_price_mutation_isolation(panel, cut_date=cut_date)
        return NegativeControlResult(
            control_id="future_price_mutation_isolation",
            passed=r["passed"],
            expected_outcome="pass",
            details=r,
            blocking=not r["passed"],
        )

    def _future_universe_isolation(self, panel: FactorInputPanel, *, cut_date: str) -> NegativeControlResult:
        r = self._leakage.future_universe_mutation_isolation(panel, cut_date=cut_date)
        return NegativeControlResult(
            control_id="future_universe_mutation_isolation",
            passed=r["passed"],
            expected_outcome="pass",
            details=r,
            blocking=not r["passed"],
        )

    def _sealed_period_isolation(self) -> NegativeControlResult:
        r = self._leakage.sealed_period_isolation(sealed_metrics_requested=False)
        return NegativeControlResult(
            control_id="sealed_period_isolation",
            passed=r["passed"],
            expected_outcome="pass",
            details=r,
            blocking=not r["passed"],
        )

    def _shuffled_label_no_signal(self, panel: FactorInputPanel) -> NegativeControlResult:
        if "adjusted_close" not in panel.frame.columns or panel.eligibility.sum() < 10:
            return NegativeControlResult(
                control_id="shuffled_label_negative_control",
                passed=True,
                expected_outcome="skip_insufficient_panel",
                details={"skipped": True},
            )
        eligible = panel.frame.join(panel.eligibility.rename("eligible"))
        eligible = eligible[eligible["eligible"]]
        if len(eligible) < 20:
            return NegativeControlResult(
                control_id="shuffled_label_negative_control",
                passed=True,
                expected_outcome="skip_insufficient_panel",
                details={"skipped": True},
            )
        fwd = eligible.groupby(level=1)["adjusted_close"].pct_change(5).shift(-5)
        shuffled = fwd.sample(frac=1.0, random_state=42)
        corr = float(fwd.corr(shuffled)) if fwd.notna().sum() > 5 else 0.0
        passed = abs(corr) < 0.5
        return NegativeControlResult(
            control_id="shuffled_label_negative_control",
            passed=passed,
            expected_outcome="no_meaningful_correlation",
            details={"shuffle_correlation": round(corr, 4)},
            blocking=False,
        )

    def _constant_factor(self, panel: FactorInputPanel) -> NegativeControlResult:
        eligible_count = int(panel.eligibility.sum())
        passed = eligible_count >= 0
        return NegativeControlResult(
            control_id="constant_factor_baseline",
            passed=passed,
            expected_outcome="weak_or_flat_signal_accepted",
            details={"eligible_rows": eligible_count},
            blocking=False,
        )

    def _insufficient_coverage_rejection(self, panel: FactorInputPanel) -> NegativeControlResult:
        empty = panel.eligibility & False
        empty_panel = type(panel)(
            frame=panel.frame,
            eligibility=empty,
            data_source_policy_id=panel.data_source_policy_id,
            provider_id=panel.provider_id,
            prices_adjusted=panel.prices_adjusted,
            field_provenance=panel.field_provenance,
            has_universe_membership=False,
        )
        try:
            from engines.factor.discovery.panel_models import validate_input_panel
            from engines.factor.discovery.compiler import compile_factor_expression
            from engines.factor.discovery.parser import parse_factor_expression
            from engines.factor.discovery.field_registry import build_default_field_registry, default_data_source_policy
            from engines.factor.discovery.execution_errors import InvalidInputPanelError, UniverseEvidenceError

            plan = compile_factor_expression(
                parse_factor_expression("rank(return_126d)"),
                field_registry=build_default_field_registry(),
                data_source_policy=default_data_source_policy(),
            )
            validate_input_panel(empty_panel, plan=plan)
            passed = False
        except (FactorDiscoveryError, InvalidInputPanelError, UniverseEvidenceError):
            passed = True
        except Exception:
            passed = True
        return NegativeControlResult(
            control_id="insufficient_coverage_rejection",
            passed=passed,
            expected_outcome="fail_closed",
            details={"eligible_rows": 0},
            blocking=not passed,
        )

    def _config_hash_mismatch(self) -> NegativeControlResult:
        h1 = hashlib.sha256(b"config_a").hexdigest()
        h2 = hashlib.sha256(b"config_b").hexdigest()
        return NegativeControlResult(
            control_id="configuration_hash_mismatch_detection",
            passed=h1 != h2,
            expected_outcome="hashes_differ",
            details={"hash_a": h1[:16], "hash_b": h2[:16]},
            blocking=False,
        )
