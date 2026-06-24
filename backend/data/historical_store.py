"""Persistent historical storage for quotes, fundamentals, and factor snapshots."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from data.db_engine import get_engine
from data.db_sessions import SessionLocal


class Base(DeclarativeBase):
    pass


class DailyQuote(Base):
    __tablename__ = "daily_quotes"
    __table_args__ = (UniqueConstraint("symbol", "date", name="uq_quote_symbol_date"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String, nullable=False, index=True)
    date = Column(String, nullable=False)
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Float, nullable=False)
    adjusted = Column(Integer, default=1)  # 1 = auto_adjusted
    updated_at = Column(DateTime, nullable=False)


class FundamentalSnapshot(Base):
    __tablename__ = "fundamental_snapshots"
    __table_args__ = (UniqueConstraint("symbol", "snapshot_date", name="uq_fund_symbol_date"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String, nullable=False, index=True)
    snapshot_date = Column(String, nullable=False)
    data_json = Column(Text, nullable=False)
    source = Column(String, default="reconciled")
    quality_score = Column(Float, nullable=True)
    updated_at = Column(DateTime, nullable=False)


class FactorSnapshot(Base):
    __tablename__ = "factor_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String, nullable=False, index=True)
    bucket = Column(String, nullable=False)
    strategy_version = Column(String, nullable=False)
    snapshot_date = Column(String, nullable=False)
    factors_json = Column(Text, nullable=False)
    score = Column(Float, nullable=True)
    updated_at = Column(DateTime, nullable=False)


class DataQualityFlag(Base):
    __tablename__ = "data_quality_flags"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String, nullable=False, index=True)
    flag_type = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False)


class JobLog(Base):
    __tablename__ = "job_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_name = Column(String, nullable=False)
    status = Column(String, nullable=False)
    message = Column(Text, default="")
    symbols_processed = Column(Integer, default=0)
    errors = Column(Integer, default=0)
    started_at = Column(DateTime, nullable=False)
    finished_at = Column(DateTime, nullable=True)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def init_historical_db() -> None:
    Base.metadata.create_all(bind=get_engine())


class HistoricalStore:
    def __init__(self, session: Session | None = None):
        self._session = session

    def _get_session(self) -> Session:
        return self._session or SessionLocal()

    def upsert_quotes(self, symbol: str, rows: list[dict]) -> int:
        if not rows:
            return 0
        session = self._get_session()
        count = 0
        try:
            sym = symbol.upper()
            now = _utcnow()
            for row in rows:
                date_str = str(row.get("date", ""))[:10]
                existing = (
                    session.query(DailyQuote)
                    .filter(DailyQuote.symbol == sym, DailyQuote.date == date_str)
                    .first()
                )
                if existing:
                    existing.open = float(row["open"])
                    existing.high = float(row["high"])
                    existing.low = float(row["low"])
                    existing.close = float(row["close"])
                    existing.volume = float(row["volume"])
                    existing.updated_at = now
                else:
                    session.add(
                        DailyQuote(
                            symbol=sym,
                            date=date_str,
                            open=float(row["open"]),
                            high=float(row["high"]),
                            low=float(row["low"]),
                            close=float(row["close"]),
                            volume=float(row["volume"]),
                            adjusted=1,
                            updated_at=now,
                        )
                    )
                count += 1
            session.commit()
            return count
        finally:
            if not self._session:
                session.close()

    def get_quotes(self, symbol: str, limit: int = 500) -> list[dict]:
        session = self._get_session()
        try:
            rows = (
                session.query(DailyQuote)
                .filter(DailyQuote.symbol == symbol.upper())
                .order_by(DailyQuote.date.desc())
                .limit(limit)
                .all()
            )
            return [
                {
                    "date": r.date,
                    "open": r.open,
                    "high": r.high,
                    "low": r.low,
                    "close": r.close,
                    "volume": r.volume,
                }
                for r in reversed(rows)
            ]
        finally:
            if not self._session:
                session.close()

    def save_fundamentals(
        self,
        symbol: str,
        data: dict,
        *,
        source: str = "reconciled",
        quality_score: float | None = None,
    ) -> None:
        session = self._get_session()
        try:
            sym = symbol.upper()
            today = _utcnow().strftime("%Y-%m-%d")
            existing = (
                session.query(FundamentalSnapshot)
                .filter(FundamentalSnapshot.symbol == sym, FundamentalSnapshot.snapshot_date == today)
                .first()
            )
            payload = json.dumps(data)
            if existing:
                existing.data_json = payload
                existing.source = source
                existing.quality_score = quality_score
                existing.updated_at = _utcnow()
            else:
                session.add(
                    FundamentalSnapshot(
                        symbol=sym,
                        snapshot_date=today,
                        data_json=payload,
                        source=source,
                        quality_score=quality_score,
                        updated_at=_utcnow(),
                    )
                )
            session.commit()
        finally:
            if not self._session:
                session.close()

    def save_factor_snapshot(
        self,
        symbol: str,
        bucket: str,
        strategy_version: str,
        factors: dict,
        score: float | None = None,
    ) -> None:
        session = self._get_session()
        try:
            session.add(
                FactorSnapshot(
                    symbol=symbol.upper(),
                    bucket=bucket,
                    strategy_version=strategy_version,
                    snapshot_date=_utcnow().strftime("%Y-%m-%d"),
                    factors_json=json.dumps(factors),
                    score=score,
                    updated_at=_utcnow(),
                )
            )
            session.commit()
        finally:
            if not self._session:
                session.close()

    def get_latest_fundamental_snapshot(self, symbol: str) -> dict | None:
        """Most recent stored fundamental snapshot for a symbol."""
        session = self._get_session()
        try:
            row = (
                session.query(FundamentalSnapshot)
                .filter(FundamentalSnapshot.symbol == symbol.upper())
                .order_by(FundamentalSnapshot.snapshot_date.desc())
                .first()
            )
            if not row or not row.data_json:
                return None
            return {
                "symbol": row.symbol,
                "snapshot_date": row.snapshot_date,
                "source": row.source,
                "quality_score": row.quality_score,
                "updated_at": row.updated_at.isoformat() if row.updated_at else None,
                "payload": json.loads(row.data_json),
            }
        finally:
            if not self._session:
                session.close()

    def get_cached_quality_scores(self, symbols: list[str]) -> dict[str, float]:
        """Batch lookup today's reconciled fundamental quality scores (cheap Stage A input)."""
        if not symbols:
            return {}
        session = self._get_session()
        try:
            today = _utcnow().strftime("%Y-%m-%d")
            unique = list(dict.fromkeys(s.upper() for s in symbols if s))
            rows = (
                session.query(FundamentalSnapshot.symbol, FundamentalSnapshot.quality_score)
                .filter(
                    FundamentalSnapshot.symbol.in_(unique),
                    FundamentalSnapshot.snapshot_date == today,
                )
                .all()
            )
            out: dict[str, float] = {}
            for sym, score in rows:
                if score is not None and float(score) > 0:
                    out[sym.upper()] = float(score)
            return out
        finally:
            if not self._session:
                session.close()

    def add_quality_flag(self, symbol: str, flag_type: str, message: str) -> None:
        session = self._get_session()
        try:
            session.add(
                DataQualityFlag(
                    symbol=symbol.upper(),
                    flag_type=flag_type,
                    message=message,
                    created_at=_utcnow(),
                )
            )
            session.commit()
        finally:
            if not self._session:
                session.close()

    def log_job(
        self,
        job_name: str,
        status: str,
        message: str = "",
        symbols_processed: int = 0,
        errors: int = 0,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
    ) -> None:
        session = self._get_session()
        try:
            session.add(
                JobLog(
                    job_name=job_name,
                    status=status,
                    message=message,
                    symbols_processed=symbols_processed,
                    errors=errors,
                    started_at=started_at or _utcnow(),
                    finished_at=finished_at,
                )
            )
            session.commit()
        finally:
            if not self._session:
                session.close()

    def get_recent_job_logs(self, limit: int = 20) -> list[dict]:
        session = self._get_session()
        try:
            rows = session.query(JobLog).order_by(JobLog.started_at.desc()).limit(limit).all()
            return [
                {
                    "job_name": r.job_name,
                    "status": r.status,
                    "message": r.message,
                    "symbols_processed": r.symbols_processed,
                    "errors": r.errors,
                    "started_at": r.started_at.isoformat() if r.started_at else None,
                    "finished_at": r.finished_at.isoformat() if r.finished_at else None,
                }
                for r in rows
            ]
        finally:
            if not self._session:
                session.close()

    def get_quality_flags(self, symbol: str, limit: int = 10) -> list[dict]:
        session = self._get_session()
        try:
            rows = (
                session.query(DataQualityFlag)
                .filter(DataQualityFlag.symbol == symbol.upper())
                .order_by(DataQualityFlag.created_at.desc())
                .limit(limit)
                .all()
            )
            return [
                {"flag_type": r.flag_type, "message": r.message, "created_at": r.created_at.isoformat()}
                for r in rows
            ]
        finally:
            if not self._session:
                session.close()
