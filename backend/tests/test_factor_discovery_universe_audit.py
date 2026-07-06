"""Universe audit tests."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.factor_discovery.staging.universe_audit import FactorDiscoveryUniverseAuditService
from tests.fixtures.factor_discovery.staging.helpers import seed_staging_fixture


def test_valid_pit_membership(isolated_backend_env):
    seed_staging_fixture(variant="valid")
    report = FactorDiscoveryUniverseAuditService().audit()
    assert report.unique_dates >= 2
    assert report.survivorship_status == "pit_membership_verified"


def test_current_list_only_detected(isolated_backend_env):
    seed_staging_fixture(variant="current_list_only")
    report = FactorDiscoveryUniverseAuditService().audit()
    assert report.current_list_only_pattern is True
    assert "constant_membership_detected" in report.blocking_codes


def test_empty_universe_blocked(isolated_backend_env):
    seed_staging_fixture(variant="empty_universe")
    report = FactorDiscoveryUniverseAuditService().audit()
    assert "universe_pit_empty" in report.blocking_codes
