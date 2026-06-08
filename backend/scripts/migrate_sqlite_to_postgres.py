#!/usr/bin/env python3
"""Copy all tables from local SQLite to PostgreSQL (one-time production migration).

Usage:
  export DATABASE_URL=postgresql+psycopg://user:pass@host:5432/stock_picker
  export SQLITE_SOURCE_PATH=backend/data_store/stock_picker.db
  python scripts/migrate_sqlite_to_postgres.py [--dry-run]

Requires: pip install psycopg[binary]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import MetaData, create_engine, inspect, select
from sqlalchemy.engine import Engine

from config import DATABASE_URL, SQLITE_SOURCE_PATH
from data.db_engine import is_postgres, reset_engine


def _sqlite_url(path: str) -> str:
    return f"sqlite:///{Path(path).resolve()}"


def copy_table(src: Engine, dst: Engine, table_name: str, *, dry_run: bool) -> int:
    meta = MetaData()
    meta.reflect(bind=src, only=[table_name])
    if table_name not in meta.tables:
        return 0
    table = meta.tables[table_name]
    dst_meta = MetaData()
    dst_meta.reflect(bind=dst, only=[table_name])
    if table_name not in dst_meta.tables:
        dst_meta.create_all(bind=dst, tables=[table])
        dst_meta.reflect(bind=dst, only=[table_name])
    dst_table = dst_meta.tables[table_name]

    rows = src.connect().execute(select(table)).mappings().all()
    if dry_run:
        print(f"  {table_name}: {len(rows)} rows (dry-run)")
        return len(rows)

    with dst.connect() as conn:
        if rows:
            conn.execute(dst_table.insert(), rows)
        conn.commit()
    print(f"  {table_name}: {len(rows)} rows copied")
    return len(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate SQLite → PostgreSQL")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--sqlite", default=SQLITE_SOURCE_PATH)
    args = parser.parse_args()

    if not is_postgres():
        print("DATABASE_URL must be a PostgreSQL URL", file=sys.stderr)
        return 1

    src_engine = create_engine(_sqlite_url(args.sqlite))
    reset_engine()
    dst_engine = create_engine(DATABASE_URL)

    from data.cache import init_db

    init_db()

    tables = inspect(src_engine).get_table_names()
    print(f"Migrating {len(tables)} tables from {args.sqlite}")
    total = 0
    for name in sorted(tables):
        total += copy_table(src_engine, dst_engine, name, dry_run=args.dry_run)
    print(f"Done — {total} rows {'would be ' if args.dry_run else ''}migrated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
