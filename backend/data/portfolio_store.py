"""Portfolio, brokerage, and decision snapshot persistence."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from data.db_engine import get_engine
from utils.datetime_util import utc_iso_z

DEFAULT_ACCOUNT_ID = 1


class PortfolioBase(DeclarativeBase):
    pass


class BrokerageAccount(PortfolioBase):
    __tablename__ = "brokerage_accounts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    label = Column(String, nullable=False, default="Primary")
    source = Column(String, nullable=False, default="manual")  # manual | csv | snaptrade
    cash_balance = Column(Float, nullable=False, default=0.0)
    last_sync_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)


class BrokerageSyncRun(PortfolioBase):
    __tablename__ = "brokerage_sync_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, nullable=False, index=True)
    source = Column(String, nullable=False)
    status = Column(String, nullable=False, default="ok")
    trades_imported = Column(Integer, nullable=False, default=0)
    trades_skipped = Column(Integer, nullable=False, default=0)
    message = Column(Text, nullable=False, default="")
    started_at = Column(DateTime, nullable=False)
    finished_at = Column(DateTime, nullable=True)


class UploadedTradeFile(PortfolioBase):
    __tablename__ = "uploaded_trade_files"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, nullable=False, index=True)
    filename = Column(String, nullable=False)
    row_count = Column(Integer, nullable=False, default=0)
    trades_imported = Column(Integer, nullable=False, default=0)
    warnings_json = Column(Text, nullable=False, default="[]")
    uploaded_at = Column(DateTime, nullable=False)


class TradeHistory(PortfolioBase):
    __tablename__ = "trade_history"
    __table_args__ = (UniqueConstraint("row_hash", name="uq_trade_row_hash"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, nullable=False, index=True)
    symbol = Column(String, nullable=False, index=True)
    side = Column(String, nullable=False)
    quantity = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    fees = Column(Float, nullable=False, default=0.0)
    executed_at = Column(DateTime, nullable=True)
    order_id = Column(String, nullable=True)
    row_hash = Column(String, nullable=False, index=True)
    source_file_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=False)


class PortfolioHoldingRow(PortfolioBase):
    __tablename__ = "portfolio_holdings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, nullable=False, index=True)
    symbol = Column(String, nullable=False, index=True)
    shares = Column(Float, nullable=False)
    avg_cost = Column(Float, nullable=False)
    bucket = Column(String, nullable=False, default="penny")
    updated_at = Column(DateTime, nullable=False)


class PortfolioSnapshot(PortfolioBase):
    __tablename__ = "portfolio_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, nullable=False, index=True)
    cash = Column(Float, nullable=False, default=0.0)
    total_value = Column(Float, nullable=False, default=0.0)
    holdings_json = Column(Text, nullable=False, default="[]")
    source = Column(String, nullable=False, default="manual")
    created_at = Column(DateTime, nullable=False)


class PortfolioDecisionSnapshot(PortfolioBase):
    __tablename__ = "portfolio_decision_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, nullable=False, index=True)
    trigger = Column(String, nullable=False, default="manual")  # manual | scheduled
    payload_json = Column(Text, nullable=False, default="{}")
    created_at = Column(DateTime, nullable=False, index=True)


_engine = get_engine()
SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def init_portfolio_db() -> None:
    PortfolioBase.metadata.create_all(bind=_engine)


def _ensure_default_account(session: Session) -> BrokerageAccount:
    acct = session.get(BrokerageAccount, DEFAULT_ACCOUNT_ID)
    now = _utcnow()
    if acct:
        return acct
    acct = BrokerageAccount(
        id=DEFAULT_ACCOUNT_ID,
        label="Robinhood",
        source="manual",
        cash_balance=0.0,
        created_at=now,
        updated_at=now,
    )
    session.add(acct)
    session.commit()
    session.refresh(acct)
    return acct


def get_or_create_account() -> dict:
    session = SessionLocal()
    try:
        acct = _ensure_default_account(session)
        return _account_dict(acct)
    finally:
        session.close()


def _account_dict(acct: BrokerageAccount) -> dict:
    return {
        "id": acct.id,
        "label": acct.label,
        "source": acct.source,
        "cash_balance": float(acct.cash_balance or 0),
        "last_sync_at": utc_iso_z(acct.last_sync_at) if acct.last_sync_at else None,
    }


def update_account_source(source: str, *, cash: float | None = None) -> dict:
    session = SessionLocal()
    try:
        acct = _ensure_default_account(session)
        acct.source = source
        acct.updated_at = _utcnow()
        if cash is not None:
            acct.cash_balance = float(cash)
        session.commit()
        session.refresh(acct)
        return _account_dict(acct)
    finally:
        session.close()


def mark_sync(account_id: int, source: str, *, trades_imported: int, trades_skipped: int, message: str) -> dict:
    session = SessionLocal()
    try:
        now = _utcnow()
        acct = session.get(BrokerageAccount, account_id) or _ensure_default_account(session)
        acct.source = source
        acct.last_sync_at = now
        acct.updated_at = now
        session.add(
            BrokerageSyncRun(
                account_id=account_id,
                source=source,
                status="ok" if trades_imported or message else "partial",
                trades_imported=trades_imported,
                trades_skipped=trades_skipped,
                message=message[:500],
                started_at=now,
                finished_at=now,
            )
        )
        session.commit()
        return _account_dict(acct)
    finally:
        session.close()


def upsert_trades(
    account_id: int,
    trades: list,
    *,
    source_file_id: int | None = None,
) -> tuple[int, int]:
    """Insert trades by row_hash; returns (imported, skipped)."""
    session = SessionLocal()
    imported = 0
    skipped = 0
    try:
        now = _utcnow()
        for t in trades:
            existing = (
                session.query(TradeHistory)
                .filter(TradeHistory.row_hash == t.row_hash)
                .first()
            )
            if existing:
                skipped += 1
                continue
            session.add(
                TradeHistory(
                    account_id=account_id,
                    symbol=t.symbol.upper(),
                    side=t.side,
                    quantity=float(t.quantity),
                    price=float(t.price),
                    fees=float(getattr(t, "fees", 0) or 0),
                    executed_at=t.executed_at,
                    order_id=getattr(t, "order_id", None),
                    row_hash=t.row_hash,
                    source_file_id=source_file_id,
                    created_at=now,
                )
            )
            imported += 1
        session.commit()
        return imported, skipped
    finally:
        session.close()


def record_upload(account_id: int, filename: str, row_count: int, trades_imported: int, warnings: list[str]) -> int:
    session = SessionLocal()
    try:
        row = UploadedTradeFile(
            account_id=account_id,
            filename=filename,
            row_count=row_count,
            trades_imported=trades_imported,
            warnings_json=json.dumps(warnings),
            uploaded_at=_utcnow(),
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return int(row.id)
    finally:
        session.close()


def list_uploads(account_id: int = DEFAULT_ACCOUNT_ID, limit: int = 20) -> list[dict]:
    session = SessionLocal()
    try:
        rows = (
            session.query(UploadedTradeFile)
            .filter(UploadedTradeFile.account_id == account_id)
            .order_by(UploadedTradeFile.uploaded_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "id": r.id,
                "filename": r.filename,
                "row_count": r.row_count,
                "trades_imported": r.trades_imported,
                "warnings": json.loads(r.warnings_json or "[]"),
                "uploaded_at": utc_iso_z(r.uploaded_at),
            }
            for r in rows
        ]
    finally:
        session.close()


def load_all_trades(account_id: int = DEFAULT_ACCOUNT_ID) -> list:
    from integrations.robinhood.models import ParsedTrade

    session = SessionLocal()
    try:
        rows = session.query(TradeHistory).filter(TradeHistory.account_id == account_id).all()
        return [
            ParsedTrade(
                symbol=r.symbol,
                side=r.side,
                quantity=r.quantity,
                price=r.price,
                fees=r.fees,
                executed_at=r.executed_at,
                order_id=r.order_id,
                row_hash=r.row_hash,
            )
            for r in rows
        ]
    finally:
        session.close()


def save_holdings(account_id: int, holdings: list, *, source: str) -> list[dict]:
    session = SessionLocal()
    try:
        now = _utcnow()
        session.query(PortfolioHoldingRow).filter(PortfolioHoldingRow.account_id == account_id).delete()
        out: list[dict] = []
        for h in holdings:
            sym = h.symbol.upper()
            row = PortfolioHoldingRow(
                account_id=account_id,
                symbol=sym,
                shares=float(h.shares),
                avg_cost=float(h.avg_cost),
                bucket=str(h.bucket),
                updated_at=now,
            )
            session.add(row)
            out.append(
                {
                    "symbol": sym,
                    "shares": float(h.shares),
                    "avg_cost": float(h.avg_cost),
                    "bucket": str(h.bucket),
                }
            )
        session.commit()
        return out
    finally:
        session.close()


def get_current_holdings(account_id: int = DEFAULT_ACCOUNT_ID) -> list[dict]:
    session = SessionLocal()
    try:
        rows = (
            session.query(PortfolioHoldingRow)
            .filter(PortfolioHoldingRow.account_id == account_id)
            .order_by(PortfolioHoldingRow.symbol)
            .all()
        )
        return [
            {
                "symbol": r.symbol,
                "shares": float(r.shares),
                "avg_cost": float(r.avg_cost),
                "bucket": r.bucket,
            }
            for r in rows
        ]
    finally:
        session.close()


def save_portfolio_snapshot(account_id: int, cash: float, total_value: float, holdings: list, source: str) -> dict:
    session = SessionLocal()
    try:
        now = _utcnow()
        row = PortfolioSnapshot(
            account_id=account_id,
            cash=cash,
            total_value=total_value,
            holdings_json=json.dumps(holdings),
            source=source,
            created_at=now,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return {"id": row.id, "created_at": utc_iso_z(row.created_at)}
    finally:
        session.close()


def save_decision_snapshot(account_id: int, trigger: str, payload: dict) -> dict:
    session = SessionLocal()
    try:
        now = _utcnow()
        row = PortfolioDecisionSnapshot(
            account_id=account_id,
            trigger=trigger,
            payload_json=json.dumps(payload),
            created_at=now,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return {"id": row.id, "created_at": utc_iso_z(row.created_at), "trigger": trigger}
    finally:
        session.close()


def get_latest_decision(account_id: int = DEFAULT_ACCOUNT_ID) -> dict | None:
    session = SessionLocal()
    try:
        row = (
            session.query(PortfolioDecisionSnapshot)
            .filter(PortfolioDecisionSnapshot.account_id == account_id)
            .order_by(PortfolioDecisionSnapshot.created_at.desc())
            .first()
        )
        if not row:
            return None
        return {
            "id": row.id,
            "trigger": row.trigger,
            "created_at": utc_iso_z(row.created_at),
            "payload": json.loads(row.payload_json or "{}"),
        }
    finally:
        session.close()


def list_decision_history(account_id: int = DEFAULT_ACCOUNT_ID, limit: int = 30) -> list[dict]:
    session = SessionLocal()
    try:
        rows = (
            session.query(PortfolioDecisionSnapshot)
            .filter(PortfolioDecisionSnapshot.account_id == account_id)
            .order_by(PortfolioDecisionSnapshot.created_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "id": r.id,
                "trigger": r.trigger,
                "created_at": utc_iso_z(r.created_at),
                "holding_count": len(json.loads(r.payload_json or "{}").get("items", [])),
            }
            for r in rows
        ]
    finally:
        session.close()


def get_account_cash(account_id: int = DEFAULT_ACCOUNT_ID) -> float:
    session = SessionLocal()
    try:
        acct = session.get(BrokerageAccount, account_id)
        return float(acct.cash_balance) if acct else 0.0
    finally:
        session.close()
