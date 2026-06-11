"""SQLite cache for market data and scan results."""
import json
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from config import FUNDAMENTALS_CACHE_TTL, PRICE_CACHE_TTL
from data.db_engine import get_engine
from utils.datetime_util import utc_iso_z, utc_now


def _utcnow() -> datetime:
    return utc_now()


class Base(DeclarativeBase):
    pass


class CacheEntry(Base):
    __tablename__ = "cache_entries"

    key = Column(String, primary_key=True)
    value = Column(Text, nullable=False)
    cached_at = Column(DateTime, nullable=False)
    ttl_seconds = Column(Float, nullable=False)


class WatchlistEntry(Base):
    __tablename__ = "watchlist"

    symbol = Column(String, primary_key=True)
    bucket = Column(String, nullable=False)
    notes = Column(Text, default="")
    added_at = Column(DateTime, nullable=False)
    price = Column(Float, nullable=True)
    score = Column(Float, nullable=True)
    summary = Column(Text, nullable=True)
    last_scanned_at = Column(DateTime, nullable=True)
    earnings_date = Column(String, nullable=True)
    days_until_earnings = Column(Float, nullable=True)
    valuation_warnings = Column(Text, nullable=True)  # JSON list


class SavedScanEntry(Base):
    __tablename__ = "saved_scans"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False, default="")
    bucket = Column(String, nullable=False, index=True)
    options_json = Column(Text, nullable=False, default="{}")
    results_json = Column(Text, nullable=False, default="[]")
    result_count = Column(Integer, nullable=False, default=0)
    strategy_version = Column(String, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False)


class SavedReportEntry(Base):
    __tablename__ = "saved_reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String, nullable=False, index=True)
    bucket = Column(String, nullable=True)
    title = Column(String, nullable=False, default="")
    notes = Column(Text, nullable=False, default="")
    report_json = Column(Text, nullable=False, default="{}")
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)


class SavedAnalyzeEntry(Base):
    __tablename__ = "saved_analyze"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String, nullable=False, index=True)
    bucket = Column(String, nullable=False, index=True)
    payload_json = Column(Text, nullable=False, default="{}")
    score = Column(Float, nullable=True)
    data_quality_score = Column(Float, nullable=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)


class TradeEntry(Base):
    __tablename__ = "trade_journal"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String, nullable=False, index=True)
    side = Column(String, nullable=False, default="long")
    entry_time = Column(DateTime, nullable=False)
    exit_time = Column(DateTime, nullable=True)
    entry_price = Column(Float, nullable=False)
    exit_price = Column(Float, nullable=True)
    quantity = Column(Float, nullable=True)
    stop_loss = Column(Float, nullable=True)
    take_profit = Column(Float, nullable=True)
    setup_tags_json = Column(Text, nullable=False, default="[]")
    thesis = Column(Text, nullable=False, default="")
    notes = Column(Text, nullable=False, default="")
    screenshot_path = Column(String, nullable=True)
    review_json = Column(Text, nullable=False, default="{}")
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)


engine = get_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def _migrate_watchlist_columns() -> None:
    """Add price/score/summary columns to existing SQLite DBs."""
    from sqlalchemy import inspect, text

    insp = inspect(engine)
    if "watchlist" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("watchlist")}
    with engine.begin() as conn:
        if "price" not in cols:
            conn.execute(text("ALTER TABLE watchlist ADD COLUMN price FLOAT"))
        if "score" not in cols:
            conn.execute(text("ALTER TABLE watchlist ADD COLUMN score FLOAT"))
        if "summary" not in cols:
            conn.execute(text("ALTER TABLE watchlist ADD COLUMN summary TEXT"))
        if "last_scanned_at" not in cols:
            conn.execute(text("ALTER TABLE watchlist ADD COLUMN last_scanned_at DATETIME"))
        if "earnings_date" not in cols:
            conn.execute(text("ALTER TABLE watchlist ADD COLUMN earnings_date VARCHAR"))
        if "days_until_earnings" not in cols:
            conn.execute(text("ALTER TABLE watchlist ADD COLUMN days_until_earnings FLOAT"))
        if "valuation_warnings" not in cols:
            conn.execute(text("ALTER TABLE watchlist ADD COLUMN valuation_warnings TEXT"))


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    _migrate_watchlist_columns()
    from data.historical_store import init_historical_db
    from data.strategy_registry import init_strategy_db

    init_historical_db()
    init_strategy_db()
    from data.portfolio_store import init_portfolio_db

    init_portfolio_db()
    from data.freshness_store import init_freshness_db

    init_freshness_db()
    from engines.quant_db import init_quant_db

    init_quant_db()
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Cache:
    def __init__(self, session: Session | None = None):
        self._session = session

    def _get_session(self) -> Session:
        if self._session:
            return self._session
        return SessionLocal()

    def get(self, key: str) -> dict | list | None:
        session = self._get_session()
        try:
            entry = session.get(CacheEntry, key)
            if not entry:
                return None
            age = (_utcnow() - entry.cached_at).total_seconds()
            if age > entry.ttl_seconds:
                session.delete(entry)
                session.commit()
                return None
            return json.loads(entry.value)
        finally:
            if not self._session:
                session.close()

    def set(self, key: str, value: dict | list, ttl_seconds: float) -> None:
        session = self._get_session()
        try:
            entry = session.get(CacheEntry, key) or CacheEntry(key=key)
            entry.value = json.dumps(value)
            entry.cached_at = _utcnow()
            entry.ttl_seconds = ttl_seconds
            session.merge(entry)
            session.commit()
        finally:
            if not self._session:
                session.close()

    def get_price_cache(self, symbol: str) -> dict | None:
        return self.get(f"price:{symbol.upper()}")

    def set_price_cache(self, symbol: str, data: dict) -> None:
        self.set(f"price:{symbol.upper()}", data, PRICE_CACHE_TTL)

    def get_fundamentals_cache(self, symbol: str) -> dict | None:
        return self.get(f"fundamentals:{symbol.upper()}")

    def set_fundamentals_cache(self, symbol: str, data: dict) -> None:
        self.set(f"fundamentals:{symbol.upper()}", data, FUNDAMENTALS_CACHE_TTL)


def get_watchlist() -> list[dict]:
    session = SessionLocal()
    try:
        rows = session.query(WatchlistEntry).order_by(WatchlistEntry.added_at.desc()).all()
        return [
            {
                "symbol": r.symbol,
                "bucket": r.bucket,
                "notes": r.notes or "",
                "added_at": utc_iso_z(r.added_at),
                "price": r.price,
                "score": r.score,
                "summary": r.summary or "",
                "last_scanned_at": utc_iso_z(r.last_scanned_at),
                "earnings_date": r.earnings_date,
                "days_until_earnings": r.days_until_earnings,
                "valuation_warnings": json.loads(r.valuation_warnings)
                if r.valuation_warnings
                else [],
            }
            for r in rows
        ]
    finally:
        session.close()


def add_to_watchlist(
    symbol: str,
    bucket: str,
    notes: str = "",
    price: float | None = None,
    score: float | None = None,
    summary: str | None = None,
    last_scanned_at: datetime | None = None,
    earnings_date: str | None = None,
    days_until_earnings: float | None = None,
    valuation_warnings: list | None = None,
) -> dict:
    session = SessionLocal()
    try:
        existing = session.get(WatchlistEntry, symbol.upper())
        entry = WatchlistEntry(
            symbol=symbol.upper(),
            bucket=bucket,
            notes=notes,
            added_at=existing.added_at if existing else _utcnow(),
            price=price,
            score=score,
            summary=summary,
            last_scanned_at=last_scanned_at or _utcnow(),
            earnings_date=earnings_date,
            days_until_earnings=days_until_earnings,
            valuation_warnings=json.dumps(valuation_warnings or []),
        )
        session.merge(entry)
        session.commit()
        return _watchlist_row_dict(entry)
    finally:
        session.close()


def _watchlist_row_dict(entry: WatchlistEntry) -> dict:
    return {
        "symbol": entry.symbol,
        "bucket": entry.bucket,
        "notes": entry.notes,
        "added_at": utc_iso_z(entry.added_at),
        "price": entry.price,
        "score": entry.score,
        "summary": entry.summary or "",
        "last_scanned_at": utc_iso_z(entry.last_scanned_at),
        "earnings_date": entry.earnings_date,
        "days_until_earnings": entry.days_until_earnings,
        "valuation_warnings": json.loads(entry.valuation_warnings)
        if entry.valuation_warnings
        else [],
    }


def save_scan_results(
    bucket: str,
    results: list,
    completed_at: str,
    ttl: float,
    strategy_version: str | None = None,
    metadata: dict | None = None,
) -> None:
    cache = Cache()
    payload: dict = {"results": results, "completed_at": completed_at}
    if strategy_version:
        payload["strategy_version"] = strategy_version
    if metadata:
        payload.update(metadata)
    cache.set(f"scan:latest:{bucket}", payload, ttl)


def get_latest_scan(bucket: str) -> dict | None:
    return Cache().get(f"scan:latest:{bucket}")


def get_latest_scan_cache_age_seconds(bucket: str) -> float | None:
    """Return seconds since the latest-scan cache row was written (ignoring TTL).

    Used by the API layer to expose `cache_age_seconds` to clients so the UI can
    decide whether to render a "stale" badge independent of the cache TTL.
    """
    session = SessionLocal()
    try:
        entry = session.get(CacheEntry, f"scan:latest:{bucket}")
        if not entry:
            return None
        age = (_utcnow() - entry.cached_at).total_seconds()
        return round(max(0.0, age), 2)
    finally:
        session.close()


def record_scan_attempt_failure(bucket: str, error: str, *, ttl_seconds: float = 3600.0) -> None:
    """Stamp the most recent failed scan attempt without touching `scan:latest:{bucket}`.

    Lets `/scan/latest/{bucket}` report `last_attempt_failed_at` so the UI can show
    "last scan attempt failed; showing prior results" instead of pretending the
    cached results are fresh.
    """
    Cache().set(
        f"scan:last_attempt:{bucket}",
        {
            "failed_at": utc_iso_z(_utcnow()),
            "error": (error or "")[:500],
        },
        ttl_seconds,
    )


def clear_scan_attempt_failure(bucket: str) -> None:
    """Remove the failed-attempt marker after a subsequent successful scan."""
    session = SessionLocal()
    try:
        entry = session.get(CacheEntry, f"scan:last_attempt:{bucket}")
        if entry:
            session.delete(entry)
            session.commit()
    finally:
        session.close()


def get_last_scan_attempt_failure(bucket: str) -> dict | None:
    return Cache().get(f"scan:last_attempt:{bucket}")


def get_watchlist_symbols() -> list[dict]:
    return get_watchlist()


def update_watchlist_notes(symbol: str, notes: str) -> dict | None:
    session = SessionLocal()
    try:
        entry = session.get(WatchlistEntry, symbol.upper())
        if not entry:
            return None
        entry.notes = notes
        session.commit()
        return _watchlist_row_dict(entry)
    finally:
        session.close()


def remove_from_watchlist(symbol: str) -> bool:
    session = SessionLocal()
    try:
        entry = session.get(WatchlistEntry, symbol.upper())
        if not entry:
            return False
        session.delete(entry)
        session.commit()
        return True
    finally:
        session.close()


def save_scan_snapshot(
    *,
    bucket: str,
    results: list[dict],
    options: dict | None = None,
    name: str | None = None,
    strategy_version: str | None = None,
    completed_at: datetime | None = None,
) -> dict:
    session = SessionLocal()
    try:
        now = _utcnow()
        entry = SavedScanEntry(
            name=(name or "").strip() or f"{bucket.title()} scan {now.strftime('%Y-%m-%d %H:%M')}",
            bucket=bucket,
            options_json=json.dumps(options or {}),
            results_json=json.dumps(results or []),
            result_count=len(results or []),
            strategy_version=strategy_version,
            completed_at=completed_at,
            created_at=now,
        )
        session.add(entry)
        session.commit()
        session.refresh(entry)
        return _saved_scan_row_dict(entry)
    finally:
        session.close()


def _saved_scan_row_dict(entry: SavedScanEntry) -> dict:
    return {
        "id": entry.id,
        "name": entry.name,
        "bucket": entry.bucket,
        "options": json.loads(entry.options_json or "{}"),
        "results": json.loads(entry.results_json or "[]"),
        "result_count": entry.result_count,
        "strategy_version": entry.strategy_version,
        "completed_at": utc_iso_z(entry.completed_at),
        "created_at": utc_iso_z(entry.created_at),
    }


def list_saved_scans(bucket: str | None = None, limit: int = 100) -> list[dict]:
    session = SessionLocal()
    try:
        q = session.query(SavedScanEntry)
        if bucket:
            q = q.filter(SavedScanEntry.bucket == bucket)
        rows = q.order_by(SavedScanEntry.created_at.desc()).limit(limit).all()
        return [_saved_scan_row_dict(r) for r in rows]
    finally:
        session.close()


def get_saved_scan(scan_id: int) -> dict | None:
    session = SessionLocal()
    try:
        row = session.get(SavedScanEntry, scan_id)
        if not row:
            return None
        return _saved_scan_row_dict(row)
    finally:
        session.close()


def delete_saved_scan(scan_id: int) -> bool:
    session = SessionLocal()
    try:
        row = session.get(SavedScanEntry, scan_id)
        if not row:
            return False
        session.delete(row)
        session.commit()
        return True
    finally:
        session.close()


def count_saved_scans() -> int:
    session = SessionLocal()
    try:
        return int(session.query(SavedScanEntry).count())
    finally:
        session.close()


def save_report_snapshot(
    *,
    symbol: str,
    report: dict,
    bucket: str | None = None,
    title: str | None = None,
    notes: str = "",
) -> dict:
    session = SessionLocal()
    try:
        now = _utcnow()
        sym = symbol.upper()
        entry = SavedReportEntry(
            symbol=sym,
            bucket=bucket,
            title=(title or "").strip() or f"{sym} report {now.strftime('%Y-%m-%d %H:%M')}",
            notes=notes,
            report_json=json.dumps(report or {}),
            created_at=now,
            updated_at=now,
        )
        session.add(entry)
        session.commit()
        session.refresh(entry)
        return _saved_report_row_dict(entry)
    finally:
        session.close()


def _saved_report_row_dict(entry: SavedReportEntry) -> dict:
    return {
        "id": entry.id,
        "symbol": entry.symbol,
        "bucket": entry.bucket,
        "title": entry.title,
        "notes": entry.notes or "",
        "report": json.loads(entry.report_json or "{}"),
        "created_at": utc_iso_z(entry.created_at),
        "updated_at": utc_iso_z(entry.updated_at),
    }


def list_saved_reports(symbol: str | None = None, limit: int = 100) -> list[dict]:
    session = SessionLocal()
    try:
        q = session.query(SavedReportEntry)
        if symbol:
            q = q.filter(SavedReportEntry.symbol == symbol.upper())
        rows = q.order_by(SavedReportEntry.updated_at.desc()).limit(limit).all()
        return [_saved_report_row_dict(r) for r in rows]
    finally:
        session.close()


def get_saved_report(report_id: int) -> dict | None:
    session = SessionLocal()
    try:
        row = session.get(SavedReportEntry, report_id)
        if not row:
            return None
        return _saved_report_row_dict(row)
    finally:
        session.close()


def update_saved_report(
    report_id: int,
    *,
    title: str | None = None,
    notes: str | None = None,
    report: dict | None = None,
) -> dict | None:
    session = SessionLocal()
    try:
        row = session.get(SavedReportEntry, report_id)
        if not row:
            return None
        if title is not None:
            row.title = title
        if notes is not None:
            row.notes = notes
        if report is not None:
            row.report_json = json.dumps(report)
        row.updated_at = _utcnow()
        session.commit()
        session.refresh(row)
        return _saved_report_row_dict(row)
    finally:
        session.close()


def delete_saved_report(report_id: int) -> bool:
    session = SessionLocal()
    try:
        row = session.get(SavedReportEntry, report_id)
        if not row:
            return False
        session.delete(row)
        session.commit()
        return True
    finally:
        session.close()


def count_saved_reports() -> int:
    session = SessionLocal()
    try:
        return int(session.query(SavedReportEntry).count())
    finally:
        session.close()


def _saved_analyze_row_dict(entry: SavedAnalyzeEntry) -> dict:
    return {
        "id": entry.id,
        "symbol": entry.symbol,
        "bucket": entry.bucket,
        "payload": json.loads(entry.payload_json or "{}"),
        "score": entry.score,
        "data_quality_score": entry.data_quality_score,
        "created_at": utc_iso_z(entry.created_at),
        "updated_at": utc_iso_z(entry.updated_at),
    }


def save_analyze_snapshot(
    *,
    symbol: str,
    bucket: str,
    payload: dict,
) -> dict:
    session = SessionLocal()
    try:
        now = _utcnow()
        sym = symbol.upper()
        row = (
            session.query(SavedAnalyzeEntry)
            .filter(SavedAnalyzeEntry.symbol == sym, SavedAnalyzeEntry.bucket == bucket)
            .order_by(SavedAnalyzeEntry.updated_at.desc())
            .first()
        )
        if not row:
            row = SavedAnalyzeEntry(
                symbol=sym,
                bucket=bucket,
                created_at=now,
                updated_at=now,
            )
            session.add(row)
        row.payload_json = json.dumps(payload or {})
        row.score = float(payload.get("score")) if payload.get("score") is not None else None
        row.data_quality_score = (
            float(payload.get("data_quality_score"))
            if payload.get("data_quality_score") is not None
            else None
        )
        row.updated_at = now
        session.commit()
        session.refresh(row)
        return _saved_analyze_row_dict(row)
    finally:
        session.close()


def list_saved_analyze(
    symbol: str | None = None,
    bucket: str | None = None,
    limit: int = 100,
) -> list[dict]:
    session = SessionLocal()
    try:
        q = session.query(SavedAnalyzeEntry)
        if symbol:
            q = q.filter(SavedAnalyzeEntry.symbol == symbol.upper())
        if bucket:
            q = q.filter(SavedAnalyzeEntry.bucket == bucket)
        rows = q.order_by(SavedAnalyzeEntry.updated_at.desc()).limit(limit).all()
        return [_saved_analyze_row_dict(r) for r in rows]
    finally:
        session.close()


def get_latest_saved_analyze(symbol: str, bucket: str | None = None) -> dict | None:
    session = SessionLocal()
    try:
        q = session.query(SavedAnalyzeEntry).filter(SavedAnalyzeEntry.symbol == symbol.upper())
        if bucket:
            q = q.filter(SavedAnalyzeEntry.bucket == bucket)
        row = q.order_by(SavedAnalyzeEntry.updated_at.desc()).first()
        if not row:
            return None
        return _saved_analyze_row_dict(row)
    finally:
        session.close()


def count_saved_analyze() -> int:
    session = SessionLocal()
    try:
        return int(session.query(SavedAnalyzeEntry).count())
    finally:
        session.close()


def _trade_row_dict(entry: TradeEntry) -> dict:
    return {
        "id": entry.id,
        "symbol": entry.symbol,
        "side": entry.side,
        "entry_time": utc_iso_z(entry.entry_time),
        "exit_time": utc_iso_z(entry.exit_time),
        "entry_price": entry.entry_price,
        "exit_price": entry.exit_price,
        "quantity": entry.quantity,
        "stop_loss": entry.stop_loss,
        "take_profit": entry.take_profit,
        "setup_tags": json.loads(entry.setup_tags_json or "[]"),
        "thesis": entry.thesis or "",
        "notes": entry.notes or "",
        "screenshot_path": entry.screenshot_path,
        "review": json.loads(entry.review_json or "{}"),
        "created_at": utc_iso_z(entry.created_at),
        "updated_at": utc_iso_z(entry.updated_at),
    }


def create_trade(
    *,
    symbol: str,
    side: str,
    entry_time: datetime,
    entry_price: float,
    exit_time: datetime | None = None,
    exit_price: float | None = None,
    quantity: float | None = None,
    stop_loss: float | None = None,
    take_profit: float | None = None,
    setup_tags: list[str] | None = None,
    thesis: str = "",
    notes: str = "",
    screenshot_path: str | None = None,
    review: dict | None = None,
) -> dict:
    session = SessionLocal()
    try:
        now = _utcnow()
        row = TradeEntry(
            symbol=symbol.upper(),
            side=side,
            entry_time=entry_time,
            exit_time=exit_time,
            entry_price=entry_price,
            exit_price=exit_price,
            quantity=quantity,
            stop_loss=stop_loss,
            take_profit=take_profit,
            setup_tags_json=json.dumps(setup_tags or []),
            thesis=thesis,
            notes=notes,
            screenshot_path=screenshot_path,
            review_json=json.dumps(review or {}),
            created_at=now,
            updated_at=now,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return _trade_row_dict(row)
    finally:
        session.close()


def list_trades(symbol: str | None = None, limit: int = 200) -> list[dict]:
    session = SessionLocal()
    try:
        q = session.query(TradeEntry)
        if symbol:
            q = q.filter(TradeEntry.symbol == symbol.upper())
        rows = q.order_by(TradeEntry.updated_at.desc()).limit(limit).all()
        return [_trade_row_dict(r) for r in rows]
    finally:
        session.close()


def get_trade(trade_id: int) -> dict | None:
    session = SessionLocal()
    try:
        row = session.get(TradeEntry, trade_id)
        if not row:
            return None
        return _trade_row_dict(row)
    finally:
        session.close()


def update_trade(
    trade_id: int,
    *,
    exit_time: datetime | None = None,
    exit_price: float | None = None,
    quantity: float | None = None,
    stop_loss: float | None = None,
    take_profit: float | None = None,
    setup_tags: list[str] | None = None,
    thesis: str | None = None,
    notes: str | None = None,
    screenshot_path: str | None = None,
    review: dict | None = None,
) -> dict | None:
    session = SessionLocal()
    try:
        row = session.get(TradeEntry, trade_id)
        if not row:
            return None
        if exit_time is not None:
            row.exit_time = exit_time
        if exit_price is not None:
            row.exit_price = exit_price
        if quantity is not None:
            row.quantity = quantity
        if stop_loss is not None:
            row.stop_loss = stop_loss
        if take_profit is not None:
            row.take_profit = take_profit
        if setup_tags is not None:
            row.setup_tags_json = json.dumps(setup_tags)
        if thesis is not None:
            row.thesis = thesis
        if notes is not None:
            row.notes = notes
        if screenshot_path is not None:
            row.screenshot_path = screenshot_path
        if review is not None:
            row.review_json = json.dumps(review)
        row.updated_at = _utcnow()
        session.commit()
        session.refresh(row)
        return _trade_row_dict(row)
    finally:
        session.close()


def delete_trade(trade_id: int) -> bool:
    session = SessionLocal()
    try:
        row = session.get(TradeEntry, trade_id)
        if not row:
            return False
        session.delete(row)
        session.commit()
        return True
    finally:
        session.close()


def count_trades() -> int:
    session = SessionLocal()
    try:
        return int(session.query(TradeEntry).count())
    finally:
        session.close()
