"""Lightweight metadata store for data-freshness timestamps."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, String, Text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from data.db_engine import get_engine
from utils.datetime_util import utc_iso_z

FRESHNESS_KEYS = (
    "portfolio_holdings",
    "latest_prices",
    "daily_decision",
    "penny_scan",
    "compounder_scan",
    "risk_metrics",
    "data_quality",
    "closed_positions",
    "home_dashboard",
)


class FreshnessBase(DeclarativeBase):
    pass


class DataFreshnessMeta(FreshnessBase):
    __tablename__ = "data_freshness_meta"

    key = Column(String, primary_key=True)
    last_updated_at = Column(DateTime, nullable=True)
    source = Column(String, nullable=False, default="system")
    extra_json = Column(Text, nullable=False, default="{}")


_engine = get_engine()
SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def init_freshness_db() -> None:
    FreshnessBase.metadata.create_all(bind=_engine)


def get_freshness_meta(key: str) -> dict | None:
    session = SessionLocal()
    try:
        row = session.get(DataFreshnessMeta, key)
        if not row:
            return None
        extra = {}
        try:
            extra = json.loads(row.extra_json or "{}")
        except json.JSONDecodeError:
            extra = {}
        return {
            "key": row.key,
            "last_updated_at": utc_iso_z(row.last_updated_at) if row.last_updated_at else None,
            "source": row.source or "system",
            "extra": extra,
        }
    finally:
        session.close()


def mark_freshness_updated(key: str, *, source: str = "system", extra: dict | None = None) -> dict:
    session = SessionLocal()
    try:
        now = _utcnow()
        row = session.get(DataFreshnessMeta, key)
        payload = json.dumps(extra or {})
        if row:
            row.last_updated_at = now
            row.source = source
            row.extra_json = payload
        else:
            session.add(
                DataFreshnessMeta(
                    key=key,
                    last_updated_at=now,
                    source=source,
                    extra_json=payload,
                )
            )
        session.commit()
        return {
            "key": key,
            "last_updated_at": utc_iso_z(now),
            "source": source,
            "extra": extra or {},
        }
    finally:
        session.close()


def set_freshness_flag(key: str, flag: str, value: bool = True) -> None:
    """Set a boolean flag in extra JSON (e.g. holdings_dirty after CSV import)."""
    session = SessionLocal()
    try:
        row = session.get(DataFreshnessMeta, key)
        extra: dict = {}
        if row:
            try:
                extra = json.loads(row.extra_json or "{}")
            except json.JSONDecodeError:
                extra = {}
        extra[flag] = value
        now = _utcnow()
        if row:
            row.extra_json = json.dumps(extra)
            if value and flag.endswith("_dirty"):
                row.last_updated_at = None
        else:
            session.add(
                DataFreshnessMeta(
                    key=key,
                    last_updated_at=None if value and flag.endswith("_dirty") else now,
                    source="system",
                    extra_json=json.dumps(extra),
                )
            )
        session.commit()
    finally:
        session.close()


def get_freshness_flag(key: str, flag: str) -> bool:
    meta = get_freshness_meta(key)
    if not meta:
        return False
    return bool((meta.get("extra") or {}).get(flag))


def clear_freshness_flag(key: str, flag: str) -> None:
    session = SessionLocal()
    try:
        row = session.get(DataFreshnessMeta, key)
        if not row:
            return
        try:
            extra = json.loads(row.extra_json or "{}")
        except json.JSONDecodeError:
            extra = {}
        extra.pop(flag, None)
        row.extra_json = json.dumps(extra)
        session.commit()
    finally:
        session.close()
