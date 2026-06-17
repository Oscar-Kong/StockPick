"""Backward-compatible re-exports — prefer core.database."""
from core.database import (  # noqa: F401
    SessionLocal,
    database_dialect,
    get_engine,
    is_postgres,
    is_sqlite,
    reset_database,
    reset_engine,
    reset_session_factory,
)
