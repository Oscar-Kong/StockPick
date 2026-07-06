"""Price audit tests."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.factor_discovery.staging.price_audit import FactorDiscoveryPriceAuditService
from tests.fixtures.factor_discovery.staging.helpers import seed_staging_fixture


def test_valid_adjusted_series(isolated_backend_env):
    seed_staging_fixture(variant="valid")
    report = FactorDiscoveryPriceAuditService().audit()
    assert report.adjusted_rows > 0
    assert "mixed_adjustment_within_symbol" not in report.blocking_codes
    assert report.audit_hash.startswith("sha256:")


def test_mixed_adjustment_blocked(isolated_backend_env):
    seed_staging_fixture(variant="mixed_adjustment")
    report = FactorDiscoveryPriceAuditService().audit()
    assert "mixed_adjustment_within_symbol" in report.blocking_codes


def test_empty_db_blocked(isolated_backend_env):
    report = FactorDiscoveryPriceAuditService().audit()
    assert "no_daily_quotes" in report.blocking_codes
