"""Portfolio, brokerage, and decision snapshot persistence."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from data.db_engine import get_engine
from data.db_sessions import SessionLocal, reset_session_factory
from utils.datetime_util import utc_iso_z


class PortfolioBase(DeclarativeBase):
    pass


class BrokerageAccount(PortfolioBase):
    __tablename__ = "brokerage_accounts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    label = Column(String, nullable=False, default="Primary")
    source = Column(String, nullable=False, default="manual")  # manual | csv | snaptrade
    cash_balance = Column(Float, nullable=False, default=0.0)
    reserved_cash = Column(Float, nullable=False, default=0.0)  # e.g. upcoming IPO allocation
    ipo_shares = Column(Float, nullable=True)
    ipo_list_price = Column(Float, nullable=True)
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
    symbol = Column(String, nullable=False, default="", index=True)
    side = Column(String, nullable=False)  # buy | sell | event (legacy: cash | income)
    quantity = Column(Float, nullable=True)
    price = Column(Float, nullable=True)
    fees = Column(Float, nullable=False, default=0.0)
    amount = Column(Float, nullable=True)
    trans_code = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    activity_date = Column(String, nullable=True)
    process_date = Column(String, nullable=True)
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


DEFAULT_ACCOUNT_ID = 1


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _migrate_trade_history_columns() -> None:
    """Add ledger columns to existing SQLite trade_history tables."""
    from sqlalchemy import inspect, text

    insp = inspect(get_engine())
    if "trade_history" not in insp.get_table_names():
        return
    existing = {c["name"] for c in insp.get_columns("trade_history")}
    alters = [
        ("amount", "FLOAT"),
        ("trans_code", "VARCHAR"),
        ("description", "TEXT"),
        ("activity_date", "VARCHAR"),
        ("process_date", "VARCHAR"),
    ]
    with get_engine().begin() as conn:
        for col, typ in alters:
            if col not in existing:
                conn.execute(text(f"ALTER TABLE trade_history ADD COLUMN {col} {typ}"))


def _migrate_brokerage_account_columns() -> None:
    from sqlalchemy import inspect, text

    insp = inspect(get_engine())
    if "brokerage_accounts" not in insp.get_table_names():
        return
    existing = {c["name"] for c in insp.get_columns("brokerage_accounts")}
    with get_engine().begin() as conn:
        if "reserved_cash" not in existing:
            conn.execute(text("ALTER TABLE brokerage_accounts ADD COLUMN reserved_cash FLOAT DEFAULT 0"))
        if "ipo_shares" not in existing:
            conn.execute(text("ALTER TABLE brokerage_accounts ADD COLUMN ipo_shares FLOAT"))
        if "ipo_list_price" not in existing:
            conn.execute(text("ALTER TABLE brokerage_accounts ADD COLUMN ipo_list_price FLOAT"))


def init_portfolio_db() -> None:
    PortfolioBase.metadata.create_all(bind=get_engine())
    _migrate_trade_history_columns()
    _migrate_brokerage_account_columns()


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
        reserved_cash=0.0,
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
        "reserved_cash": float(getattr(acct, "reserved_cash", 0) or 0),
        "ipo_shares": float(acct.ipo_shares) if getattr(acct, "ipo_shares", None) is not None else None,
        "ipo_list_price": float(acct.ipo_list_price) if getattr(acct, "ipo_list_price", None) is not None else None,
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
                    symbol=(t.symbol or "").upper(),
                    side=t.side,
                    quantity=float(t.quantity) if t.quantity is not None else None,
                    price=float(t.price) if t.price is not None else None,
                    fees=float(getattr(t, "fees", 0) or 0),
                    amount=float(getattr(t, "amount", 0) or 0) or None,
                    trans_code=getattr(t, "trans_code", None),
                    description=getattr(t, "description", None),
                    activity_date=getattr(t, "activity_date", None),
                    process_date=getattr(t, "process_date", None),
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


def _parsed_from_trade_history(r: TradeHistory) -> "ParsedCsvRow":
    from integrations.robinhood.models import ParsedCsvRow, normalize_row_type

    row_type = normalize_row_type(r.side)
    qty = None if row_type == "event" and (r.quantity or 0) == 0 else r.quantity
    price = None if row_type == "event" and (r.price or 0) == 0 else r.price
    return ParsedCsvRow(
        activity_date=r.activity_date or "",
        process_date=r.process_date or "",
        instrument=r.symbol or "",
        description=r.description or "",
        trans_code=(r.trans_code or r.side or "").upper(),
        quantity=qty,
        price=price,
        amount=float(r.amount or 0),
        row_type=row_type,
        row_hash=r.row_hash,
        executed_at=r.executed_at,
    )


def repair_ledger_fill_prices(account_id: int = DEFAULT_ACCOUNT_ID) -> int:
    """Persist Amount/Quantity fill prices for rows with wrong Robinhood Price column."""
    from integrations.robinhood.ledger_dedupe import apply_effective_fill_price

    session = SessionLocal()
    updated = 0
    try:
        rows = (
            session.query(TradeHistory)
            .filter(TradeHistory.account_id == account_id, TradeHistory.side.in_(("buy", "sell")))
            .all()
        )
        for r in rows:
            parsed = apply_effective_fill_price(_parsed_from_trade_history(r))
            corrected = float(parsed.price or 0)
            if corrected > 0 and abs(corrected - float(r.price or 0)) > 1e-6:
                r.price = corrected
                updated += 1
        if updated:
            session.commit()
        return updated
    finally:
        session.close()


def upsert_ledger_rows(
    account_id: int,
    rows: list,
    *,
    source_file_id: int | None = None,
) -> tuple[int, int]:
    """Insert all parsed CSV rows (buy/sell/cash/income) by row_hash and semantic key."""
    from integrations.robinhood.models import ParsedCsvRow
    from integrations.robinhood.ledger_dedupe import (
        apply_effective_fill_price,
        dedupe_parsed_rows,
        is_incomplete_ghost_row,
        semantic_ledger_key,
    )

    rows, _ = dedupe_parsed_rows([r for r in rows if isinstance(r, ParsedCsvRow)])

    session = SessionLocal()
    imported = 0
    skipped = 0
    updated = 0
    try:
        now = _utcnow()
        existing_hashes = {
            h
            for (h,) in session.query(TradeHistory.row_hash)
            .filter(TradeHistory.account_id == account_id)
            .all()
            if h
        }
        existing_semantic: dict[tuple, TradeHistory] = {}
        for r in session.query(TradeHistory).filter(TradeHistory.account_id == account_id).all():
            parsed = apply_effective_fill_price(_parsed_from_trade_history(r))
            existing_semantic[semantic_ledger_key(parsed)] = r

        for r in rows:
            if not isinstance(r, ParsedCsvRow):
                continue
            apply_effective_fill_price(r)
            if is_incomplete_ghost_row(r):
                skipped += 1
                continue
            if r.row_hash in existing_hashes:
                skipped += 1
                continue
            sem_key = semantic_ledger_key(r)
            existing = existing_semantic.get(sem_key)
            if existing is not None:
                corrected = float(r.price or 0)
                if corrected > 0 and abs(corrected - float(existing.price or 0)) > 1e-6:
                    existing.price = corrected
                    updated += 1
                skipped += 1
                continue
            side = "event" if r.row_type == "event" else r.row_type
            if side in ("cash", "income"):
                side = "event"
            qty = r.quantity if r.quantity is not None else 0.0
            pr = r.price if r.price is not None else 0.0
            session.add(
                TradeHistory(
                    account_id=account_id,
                    symbol=(r.instrument or "").upper(),
                    side=side,
                    quantity=qty,
                    price=pr,
                    amount=r.amount,
                    trans_code=r.trans_code,
                    description=r.description,
                    activity_date=r.activity_date,
                    process_date=r.process_date,
                    executed_at=r.executed_at,
                    row_hash=r.row_hash,
                    source_file_id=source_file_id,
                    created_at=now,
                )
            )
            existing_hashes.add(r.row_hash)
            imported += 1
        if imported or updated:
            session.commit()
        return imported, skipped
    finally:
        session.close()


def purge_duplicate_trades(account_id: int = DEFAULT_ACCOUNT_ID) -> int:
    """Remove duplicate ledger rows from DB, keeping the most complete row per trade."""
    from integrations.robinhood.models import ParsedCsvRow
    from integrations.robinhood.ledger_dedupe import (
        _row_completeness,
        apply_effective_fill_price,
        is_incomplete_ghost_row,
        semantic_ledger_key,
    )

    session = SessionLocal()
    try:
        db_rows = (
            session.query(TradeHistory)
            .filter(TradeHistory.account_id == account_id)
            .order_by(TradeHistory.id)
            .all()
        )
        best_id: dict[tuple, tuple[int, ParsedCsvRow]] = {}
        for r in db_rows:
            parsed = apply_effective_fill_price(_parsed_from_trade_history(r))
            if is_incomplete_ghost_row(parsed):
                continue
            key = semantic_ledger_key(parsed)
            prev = best_id.get(key)
            if prev is None or _row_completeness(parsed) > _row_completeness(prev[1]):
                best_id[key] = (int(r.id), parsed)

        keep_ids = {v[0] for v in best_id.values()}
        removed = 0
        for r in db_rows:
            parsed = apply_effective_fill_price(_parsed_from_trade_history(r))
            if is_incomplete_ghost_row(parsed) or int(r.id) not in keep_ids:
                session.delete(r)
                removed += 1
        if removed:
            session.commit()
        return removed
    finally:
        session.close()


def clear_trade_ledger(account_id: int = DEFAULT_ACCOUNT_ID) -> int:
    """Remove all ledger rows for an account (full reset)."""
    session = SessionLocal()
    try:
        removed = (
            session.query(TradeHistory)
            .filter(TradeHistory.account_id == account_id)
            .delete(synchronize_session=False)
        )
        session.commit()
        return int(removed or 0)
    finally:
        session.close()


def clear_csv_sourced_ledger(account_id: int = DEFAULT_ACCOUNT_ID) -> int:
    """Remove CSV-imported ledger rows; keep manual journal entries."""
    from integrations.robinhood.journal_verifier import is_manual_journal_ledger_row

    session = SessionLocal()
    try:
        rows = session.query(TradeHistory).filter(TradeHistory.account_id == account_id).all()
        removed = 0
        for r in rows:
            if is_manual_journal_ledger_row(
                trans_code=r.trans_code,
                description=r.description,
                row_hash=r.row_hash,
            ):
                continue
            session.delete(r)
            removed += 1
        if removed:
            session.commit()
        return removed
    finally:
        session.close()


def load_all_ledger_rows(account_id: int = DEFAULT_ACCOUNT_ID) -> list:
    from integrations.robinhood.models import ParsedCsvRow
    from integrations.robinhood.ledger_dedupe import apply_effective_fill_price, dedupe_parsed_rows

    session = SessionLocal()
    try:
        rows = (
            session.query(TradeHistory)
            .filter(TradeHistory.account_id == account_id)
            .order_by(TradeHistory.executed_at, TradeHistory.id)
            .all()
        )
        out: list[ParsedCsvRow] = []
        for r in rows:
            out.append(apply_effective_fill_price(_parsed_from_trade_history(r)))
        deduped, _ = dedupe_parsed_rows(out)
        return deduped
    finally:
        session.close()


def set_account_cash(account_id: int, cash: float) -> None:
    session = SessionLocal()
    try:
        acct = _ensure_default_account(session)
        acct.cash_balance = float(cash)
        acct.updated_at = _utcnow()
        session.commit()
    finally:
        session.close()


def set_account_reserved_cash(account_id: int, reserved: float) -> None:
    session = SessionLocal()
    try:
        acct = _ensure_default_account(session)
        acct.reserved_cash = max(0.0, float(reserved))
        acct.updated_at = _utcnow()
        session.commit()
    finally:
        session.close()


def set_account_ipo_order(
    account_id: int,
    *,
    shares: float | None,
    list_price: float | None,
    reserved: float,
) -> None:
    session = SessionLocal()
    try:
        acct = _ensure_default_account(session)
        acct.reserved_cash = max(0.0, float(reserved))
        acct.ipo_shares = float(shares) if shares is not None and shares > 0 else None
        acct.ipo_list_price = float(list_price) if list_price is not None and list_price > 0 else None
        acct.updated_at = _utcnow()
        session.commit()
    finally:
        session.close()


def get_account_reserved_cash(account_id: int = DEFAULT_ACCOUNT_ID) -> float:
    session = SessionLocal()
    try:
        acct = session.get(BrokerageAccount, account_id)
        return float(getattr(acct, "reserved_cash", 0) or 0) if acct else 0.0
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
    from integrations.robinhood.ledger_dedupe import apply_effective_fill_price

    session = SessionLocal()
    try:
        rows = (
            session.query(TradeHistory)
            .filter(TradeHistory.account_id == account_id, TradeHistory.side.in_(("buy", "sell")))
            .all()
        )
        out: list[ParsedTrade] = []
        for r in rows:
            parsed = apply_effective_fill_price(_parsed_from_trade_history(r))
            out.append(
                ParsedTrade(
                    symbol=r.symbol,
                    side=r.side,
                    quantity=float(parsed.quantity or 0),
                    price=float(parsed.price or 0),
                    fees=r.fees,
                    executed_at=r.executed_at,
                    order_id=r.order_id,
                    row_hash=r.row_hash,
                    trans_code=r.trans_code or "",
                    amount=float(r.amount or 0),
                    description=r.description or "",
                )
            )
        return out
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


def ledger_has_row_hash(row_hash: str, account_id: int = DEFAULT_ACCOUNT_ID) -> bool:
    """True when a ledger row with this content hash exists (journal sync idempotency)."""
    if not row_hash:
        return False
    session = SessionLocal()
    try:
        return (
            session.query(TradeHistory.id)
            .filter(TradeHistory.account_id == account_id, TradeHistory.row_hash == row_hash)
            .first()
            is not None
        )
    finally:
        session.close()


def rename_holding_symbol(old_symbol: str, new_symbol: str, account_id: int = DEFAULT_ACCOUNT_ID) -> int:
    """Rename a symbol across ledger rows and saved holdings."""
    old = (old_symbol or "").upper().strip()
    new = (new_symbol or "").upper().strip()
    if not old or not new or old == new:
        return 0
    session = SessionLocal()
    updated = 0
    try:
        for row in session.query(TradeHistory).filter(
            TradeHistory.account_id == account_id, TradeHistory.symbol == old
        ):
            row.symbol = new
            updated += 1
        holding = (
            session.query(PortfolioHoldingRow)
            .filter(PortfolioHoldingRow.account_id == account_id, PortfolioHoldingRow.symbol == old)
            .first()
        )
        if holding:
            conflict = (
                session.query(PortfolioHoldingRow)
                .filter(PortfolioHoldingRow.account_id == account_id, PortfolioHoldingRow.symbol == new)
                .first()
            )
            if conflict:
                conflict.shares = float(conflict.shares) + float(holding.shares)
                session.delete(holding)
            else:
                holding.symbol = new
            updated += 1
        if updated:
            session.commit()
        return updated
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


def get_latest_portfolio_snapshot(account_id: int = DEFAULT_ACCOUNT_ID) -> dict | None:
    session = SessionLocal()
    try:
        row = (
            session.query(PortfolioSnapshot)
            .filter(PortfolioSnapshot.account_id == account_id)
            .order_by(PortfolioSnapshot.created_at.desc())
            .first()
        )
        if not row:
            return None
        data = json.loads(row.holdings_json or "{}")
        if isinstance(data, list):
            holdings = data
            closed = []
            misc_events = []
        else:
            holdings = data.get("holdings") or []
            closed = data.get("closed_positions") or []
            misc_events = data.get("misc_events") or []
        return {
            "cash": float(row.cash),
            "total_value": float(row.total_value),
            "holdings": holdings,
            "closed_positions": closed,
            "misc_events": misc_events,
            "source": row.source,
            "created_at": utc_iso_z(row.created_at),
        }
    finally:
        session.close()


def save_portfolio_snapshot(
    account_id: int,
    cash: float,
    total_value: float,
    holdings: list,
    source: str,
    *,
    closed_positions: list | None = None,
    extra: dict | None = None,
) -> dict:
    session = SessionLocal()
    try:
        now = _utcnow()
        payload = {"holdings": holdings, "closed_positions": closed_positions or []}
        if extra:
            payload.update(extra)
        row = PortfolioSnapshot(
            account_id=account_id,
            cash=cash,
            total_value=total_value,
            holdings_json=json.dumps(payload),
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
