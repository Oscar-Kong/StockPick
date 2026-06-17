"""Demo database seeding and isolation tests."""
from __future__ import annotations

import pytest


def test_normal_mode_does_not_seed_demo_data(isolated_backend_env, monkeypatch):
    import config

    monkeypatch.setattr(config, "DEMO_MODE", False, raising=False)
    monkeypatch.setattr(config, "DEMO_SEED_DATA", False, raising=False)

    from services.demo_seed_service import seed_demo_data_if_needed
    from data.portfolio_store import get_current_holdings, SessionLocal, TradeHistory

    seed_demo_data_if_needed()
    assert get_current_holdings() == []
    session = SessionLocal()
    try:
        assert session.query(TradeHistory).count() == 0
    finally:
        session.close()


def test_empty_demo_database_gets_seeded(demo_client):
    from data.portfolio_store import get_current_holdings

    holdings = get_current_holdings()
    assert len(holdings) >= 1


def test_demo_seed_idempotent(demo_client):
    from services.demo_seed_service import seed_demo_data_if_needed
    from data.portfolio_store import get_current_holdings

    before = get_current_holdings()
    seed_demo_data_if_needed()
    after = get_current_holdings()
    assert before == after


def test_recreated_sqlite_starts(isolated_backend_env, monkeypatch, tmp_path):
    import config
    from data.db_sessions import reset_session_factory
    from data.db_engine import reset_engine
    from data.portfolio_store import init_portfolio_db

    db_path = tmp_path / "recreated.db"
    db_url = f"sqlite:///{db_path}"
    monkeypatch.setattr(config, "DATABASE_URL", db_url, raising=False)
    reset_engine()
    reset_session_factory()
    init_portfolio_db()
    assert db_path.exists()
