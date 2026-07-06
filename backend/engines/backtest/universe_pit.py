"""Point-in-time universe (survivorship bias reduction)."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from data.db_engine import get_engine
from engines.quant_models import UniversePit

logger = logging.getLogger(__name__)


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def seed_universe_pit(symbols: list[str], *, as_of_date: str | None = None, bucket_hint: str = "penny") -> int:
    """Insert active symbols for a snapshot date."""
    from engines.quant_db import init_quant_db

    init_quant_db()
    engine = get_engine()
    as_of = as_of_date or _today()
    count = 0
    with Session(engine) as session:
        for sym in symbols:
            sym = sym.upper()
            existing = (
                session.query(UniversePit)
                .filter(UniversePit.as_of_date == as_of, UniversePit.symbol == sym)
                .first()
            )
            if existing:
                existing.is_active = True
                existing.bucket_hint = bucket_hint
            else:
                session.add(
                    UniversePit(
                        as_of_date=as_of,
                        symbol=sym,
                        bucket_hint=bucket_hint,
                        is_active=True,
                    )
                )
            count += 1
        session.commit()
    return count


def active_symbols_on_date(symbols: list[str], as_of_date: str) -> list[str]:
    """Filter to symbols marked active in universe_pit for date (passthrough if empty)."""
    engine = get_engine()
    with Session(engine) as session:
        rows = (
            session.query(UniversePit.symbol)
            .filter(UniversePit.as_of_date == as_of_date, UniversePit.is_active == True)  # noqa: E712
            .all()
        )
        if not rows:
            return symbols
        allowed = {r[0].upper() for r in rows}
        return [s for s in symbols if s.upper() in allowed]


def ensure_pit_seeded(symbols: list[str]) -> None:
    """Seed today's pit from symbol list if empty."""
    try:
        seed_universe_pit(symbols)
    except Exception as exc:
        logger.debug("universe_pit seed skipped: %s", exc)
