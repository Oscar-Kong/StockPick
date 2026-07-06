"""Shared pytest fixtures — isolated DB, env, and runtime state per test."""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

_DB_MODULES = (
    "data.db_engine",
    "data.db_sessions",
    "data.cache",
    "data.portfolio_store",
    "data.historical_store",
    "data.strategy_registry",
    "data.freshness_store",
    "engines.quant_db",
)


def _reload_db_modules() -> None:
    importlib.reload(importlib.import_module("data.db_engine"))
    for name in _DB_MODULES[1:]:
        if name in sys.modules:
            importlib.reload(sys.modules[name])


def _reset_runtime_state() -> None:
    from data.db_engine import reset_engine

    reset_engine()
    try:
        from data.db_sessions import reset_session_factory

        reset_session_factory()
    except Exception:
        pass
    try:
        from data.portfolio_store import reset_session_factory as reset_portfolio_sessions

        reset_portfolio_sessions()
    except Exception:
        pass
    try:
        from utils.rate_limit import reset_rate_limits

        reset_rate_limits()
    except Exception:
        pass
    try:
        from data.universe import _get_universe_cached

        _get_universe_cached.cache_clear()
    except Exception:
        pass
    try:
        import config
        from utils.runtime_flags import get_registry

        get_registry(config.DATA_DIR).reset()
    except Exception:
        pass


@pytest.fixture(autouse=True)
def isolated_backend_env(monkeypatch, tmp_path, request):
    """Fresh SQLite DB and non-demo defaults for every test unless overridden."""
    if request.node.get_closest_marker("no_db_isolation"):
        yield
        return

    db_path = tmp_path / "pytest.db"
    db_url = f"sqlite:///{db_path}"

    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DEMO_MODE", "false")
    monkeypatch.setenv("DEMO_SEED_DATA", "false")
    monkeypatch.setenv("SCHEDULER_ENABLED", "false")
    monkeypatch.setenv("LISTING_MASTER_ENABLED", "false")
    monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)

    import config

    monkeypatch.setattr(config, "DATABASE_URL", db_url, raising=False)
    monkeypatch.setattr(config, "DEMO_MODE", False, raising=False)
    monkeypatch.setattr(config, "DEMO_SEED_DATA", False, raising=False)
    monkeypatch.setattr(config, "APP_ENV", "test", raising=False)

    _reset_runtime_state()
    _reload_db_modules()

    from data.cache import init_db

    init_db()

    yield

    _reset_runtime_state()


@pytest.fixture
def demo_client(isolated_backend_env, monkeypatch):
    """TestClient with DEMO_MODE enabled on an isolated database."""
    import config

    monkeypatch.setattr(config, "DEMO_MODE", True, raising=False)
    monkeypatch.setattr(config, "DEMO_SEED_DATA", True, raising=False)
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("DEMO_SEED_DATA", "true")
    monkeypatch.setattr(config, "ALLOWED_ORIGINS", ["http://localhost:18730"], raising=False)

    from services.demo_seed_service import seed_demo_data_if_needed

    seed_demo_data_if_needed()

    from fastapi.testclient import TestClient
    from main import app

    return TestClient(app)
