"""Universe audit scalability tests."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from data.db_engine import get_engine
from engines.quant_models import UniversePit
from services.factor_discovery.staging.audit_limits import MAXIMUM_FLAGGED_EXAMPLES_PER_CATEGORY
from services.factor_discovery.staging.universe_audit import FactorDiscoveryUniverseAuditService
from sqlalchemy.orm import Session
from tests.fixtures.factor_discovery.staging.helpers import seed_staging_fixture


def test_universe_audit_no_full_table_all(isolated_backend_env):
    seed_staging_fixture(variant="valid")
    calls: list[str] = []
    original_query = Session.query

    def tracking_query(self, *entities):
        q = original_query(self, *entities)
        if entities and entities[0] is UniversePit:
            orig_all = q.all

            def wrapped_all():
                calls.append("UniversePit.all")
                return orig_all()

            q.all = wrapped_all  # type: ignore[method-assign]
        return q

    with patch.object(Session, "query", tracking_query):
        report = FactorDiscoveryUniverseAuditService().audit()

    assert report.unique_dates >= 2
    assert "UniversePit.all" not in calls
    assert len(report.symbols_without_quotes) <= MAXIMUM_FLAGGED_EXAMPLES_PER_CATEGORY


def test_universe_audit_entry_exit_events(isolated_backend_env):
    seed_staging_fixture(variant="valid")
    report = FactorDiscoveryUniverseAuditService().audit()
    assert report.entry_events >= 1
    assert report.exit_events >= 1
