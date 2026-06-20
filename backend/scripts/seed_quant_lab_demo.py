#!/usr/bin/env python3
"""Seed a local SQLite database with deterministic Quant Lab demo evidence."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

DEFAULT_DB = BACKEND.parent / "storage" / "dev" / "quant_lab_demo.db"


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed Quant Lab demo database")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="SQLite database path")
    parser.add_argument("--sleeve", default="medium", choices=["penny", "medium", "compounder"])
    args = parser.parse_args()

    args.db.parent.mkdir(parents=True, exist_ok=True)
    if args.db.exists():
        args.db.unlink()
    db_url = f"sqlite:///{args.db}"
    os.environ["DATABASE_URL"] = db_url
    os.environ.setdefault("APP_ENV", "development")
    os.environ.setdefault("DEMO_MODE", "false")

    import config

    config.DATABASE_URL = db_url

    from data.cache import init_db
    from tests.fixtures.quant_lab_fixtures import seed_quant_lab_demo

    init_db()
    summary = seed_quant_lab_demo(sleeve=args.sleeve)
    print(f"Seeded Quant Lab demo DB: {args.db}")
    for k, v in summary.items():
        print(f"  {k}: {v}")
    print("\nStart backend with:")
    print(f"  DATABASE_URL=sqlite:///{args.db} python -m uvicorn main:app --port 18731")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
