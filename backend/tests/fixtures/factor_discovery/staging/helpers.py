"""Deterministic staging fixture seeding for tests."""
from __future__ import annotations

from pathlib import Path

from data.db_engine import get_engine
from data.historical_store import DailyQuote
from engines.quant_models import UniversePit
from sqlalchemy.orm import Session

FIXTURE_DIR = Path(__file__).resolve().parent / "staging"


def seed_staging_fixture(*, variant: str = "valid") -> dict:
    """Seed isolated DB with a small staging dataset."""
    if variant == "long_history":
        sessions = []
        from datetime import date, timedelta

        cur = date(2020, 1, 2)
        while len(sessions) < 140:
            if cur.weekday() < 5:
                sessions.append(cur.isoformat())
            cur += timedelta(days=1)
    else:
        sessions = [f"2020-01-{d:02d}" for d in range(2, 11)]  # 9 sessions
    symbols = ["AAA", "BBB", "CCC", "EXIT"]
    with Session(get_engine()) as session:
        session.query(DailyQuote).delete()
        session.query(UniversePit).delete()
        session.commit()
        for sym in symbols:
            for i, d in enumerate(sessions):
                close = 100 + i + (0.5 if sym == "BBB" else 0)
                if variant == "mixed_adjustment" and sym == "BBB" and i == 4:
                    adj = 0
                else:
                    adj = 1
                if variant == "split_like" and sym == "AAA" and i == 5:
                    close = close * 0.5
                session.add(
                    DailyQuote(
                        symbol=sym,
                        date=d,
                        open=close,
                        high=close + 1,
                        low=close - 1,
                        close=close,
                        volume=1_000_000 + i * 1000,
                        adjusted=adj,
                        updated_at=__import__("datetime").datetime.utcnow(),
                    )
                )
        # PIT universe with entry/exit for EXIT symbol
        for d in sessions:
            for sym in ["AAA", "BBB", "CCC"]:
                session.add(UniversePit(as_of_date=d, symbol=sym, is_active=True, bucket_hint="staging"))
            if d <= sessions[6]:
                session.add(UniversePit(as_of_date=d, symbol="EXIT", is_active=True, bucket_hint="staging"))
        if variant == "current_list_only":
            session.query(UniversePit).delete()
            for d in sessions:
                for sym in symbols:
                    session.add(UniversePit(as_of_date=d, symbol=sym, is_active=True, bucket_hint="staging"))
        if variant == "empty_universe":
            session.query(UniversePit).delete()
        session.commit()
    return {"sessions": sessions, "symbols": symbols, "variant": variant}
