"""Shared SQLAlchemy session factory bound to the current DATABASE_URL."""
from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from data.db_engine import get_engine

_sessionmaker: sessionmaker | None = None
_bound_url: str | None = None


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
