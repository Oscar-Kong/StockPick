"""Price audit scalability tests."""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from data.db_engine import get_engine
from data.historical_store import DailyQuote
from services.factor_discovery.staging.audit_limits import MAXIMUM_FLAGGED_EXAMPLES_PER_CATEGORY
from services.factor_discovery.staging.price_audit import FactorDiscoveryPriceAuditService
from sqlalchemy.orm import Session


def _seed_large_quotes(n_symbols: int = 60, n_days: int = 40) -> None:
    from datetime import date, timedelta

    start = date(2020, 1, 2)
    day_strings = []
    cur = start
    while len(day_strings) < n_days:
        if cur.weekday() < 5:
            day_strings.append(cur.isoformat())
        cur += timedelta(days=1)
    with Session(get_engine()) as session:
        session.query(DailyQuote).delete()
        session.commit()
        for s in range(n_symbols):
            sym = f"L{s:03d}"
            for d, day in enumerate(day_strings):
                close = 10.0 + s + d * 0.01
                session.add(
                    DailyQuote(
                        symbol=sym,
                        date=day,
                        open=close,
                        high=close + 1,
                        low=close - 1,
                        close=close,
                        volume=1000,
                        adjusted=1,
                        updated_at=datetime.utcnow(),
                    )
                )
        session.commit()


def test_price_audit_no_dailyquote_all_materialization(isolated_backend_env):
    _seed_large_quotes(n_symbols=80, n_days=50)
    calls: list[str] = []

    original_query = Session.query

    def tracking_query(self, *entities):
        q = original_query(self, *entities)
        if entities and entities[0] is DailyQuote:
            orig_all = q.all

            def wrapped_all():
                calls.append("DailyQuote.all")
                return orig_all()

            q.all = wrapped_all  # type: ignore[method-assign]
        return q

    with patch.object(Session, "query", tracking_query):
        report = FactorDiscoveryPriceAuditService().audit(sample_jump_symbols=10)

    assert report.total_rows == 80 * 50
    assert "DailyQuote.all" not in calls
    assert len(report.suspicious_jumps) <= MAXIMUM_FLAGGED_EXAMPLES_PER_CATEGORY


def test_price_audit_sample_size_bounded(isolated_backend_env):
    _seed_large_quotes(n_symbols=100, n_days=30)
    small = FactorDiscoveryPriceAuditService().audit(sample_jump_symbols=5)
    large = FactorDiscoveryPriceAuditService().audit(sample_jump_symbols=50)
    assert small.total_rows == large.total_rows
    assert len(small.suspicious_jumps) <= MAXIMUM_FLAGGED_EXAMPLES_PER_CATEGORY
    assert len(large.suspicious_jumps) <= MAXIMUM_FLAGGED_EXAMPLES_PER_CATEGORY


def test_price_audit_deterministic_hash(isolated_backend_env):
    _seed_large_quotes(n_symbols=10, n_days=10)
    a = FactorDiscoveryPriceAuditService().audit()
    b = FactorDiscoveryPriceAuditService().audit()
    assert a.audit_hash == b.audit_hash
    assert a.total_rows == b.total_rows
