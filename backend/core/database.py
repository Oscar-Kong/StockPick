"""SQLAlchemy engine and session factory."""
from __future__ import annotations

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from config import DATABASE_POOL_SIZE

_engine: Engine | None = None
_engine_url: str | None = None
_sessionmaker: sessionmaker | None = None
_bound_url: str | None = None


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
    global _engine, _engine_url
    if _engine is not None:
        _engine.dispose()
        _engine = None
    _engine_url = None


def SessionLocal() -> Session:
    global _sessionmaker, _bound_url
    from config import DATABASE_URL

    url = DATABASE_URL
    if _sessionmaker is None or _bound_url != url:
        _sessionmaker = sessionmaker(bind=get_engine(), autoflush=False, autocommit=False)
        _bound_url = url
    return _sessionmaker()


def reset_session_factory() -> None:
    global _sessionmaker, _bound_url
    _sessionmaker = None
    _bound_url = None


def reset_database() -> None:
    """Reset engine and session factory (tests)."""
    reset_engine()
    reset_session_factory()
