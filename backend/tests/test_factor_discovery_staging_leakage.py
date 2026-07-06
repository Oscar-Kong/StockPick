"""Leakage audit tests."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.factor_discovery.staging.leakage_audit import FactorDiscoveryLeakageAuditService
from tests.fixtures.factor_discovery.validation.validation_panel_builder import build_validation_context


def test_outcome_fields_absent():
    panel = build_validation_context()["panel"]
    result = FactorDiscoveryLeakageAuditService().assert_outcome_fields_absent(panel)
    assert result["passed"] is True


def test_future_price_mutation_isolation():
    panel = build_validation_context()["panel"]
    dates = sorted({str(d.date())[:10] for d in panel.frame.index.get_level_values(0).unique()})
    cut = dates[len(dates) // 2]
    result = FactorDiscoveryLeakageAuditService().future_price_mutation_isolation(panel, cut_date=cut)
    assert result["passed"] is True


def test_sealed_isolation():
    result = FactorDiscoveryLeakageAuditService().sealed_period_isolation()
    assert result["passed"] is True
    assert result["sealed_metrics_computed"] is False
