"""Shared SQLAlchemy engine — SQLite (local) or PostgreSQL (production)."""
from __future__ import annotations

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine

from config import DATABASE_POOL_SIZE

_engine: Engine | None = None
_engine_url: str | None = None


def _database_url() -> str:
    from config import DATABASE_URL

    return DATABASE_URL


def database_dialect() -> str:
    url = _database_url().lower()
    if url.startswith("postgresql") or url.startswith("postgres"):
        return "postgresql"
    return "sqlite"


def is_postgres() -> bool:
    return database_dialect() == "postgresql"


def is_sqlite() -> bool:
    return database_dialect() == "sqlite"


def get_engine() -> Engine:
    global _engine, _engine_url
    url = _database_url()
    if _engine is not None and _engine_url == url:
        return _engine

    if _engine is not None:
        _engine.dispose()
        _engine = None

    kwargs: dict = {"pool_pre_ping": True}
    if is_sqlite():
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        kwargs["pool_size"] = DATABASE_POOL_SIZE
        kwargs["max_overflow"] = max(2, DATABASE_POOL_SIZE // 2)

    _engine = create_engine(url, **kwargs)
    _engine_url = url

    if is_sqlite():

        @event.listens_for(_engine, "connect")
        def _sqlite_wal(dbapi_conn, _record) -> None:
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA busy_timeout=60000")
            cur.close()

    return _engine


def reset_engine() -> None:
    """Dispose cached engine (tests or post-migration)."""
    global _engine, _engine_url
    if _engine is not None:
        _engine.dispose()
        _engine = None
    _engine_url = None
