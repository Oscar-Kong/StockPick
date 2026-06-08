"""Seed S&P 500 ticker list into SQLite cache for universe expansion."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from data.cache import Cache, init_db


def fetch_sp500_symbols() -> list[str]:
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    tables = pd.read_html(url)
    df = tables[0]
    symbols = df["Symbol"].astype(str).str.replace(".", "-", regex=False).tolist()
    return sorted(set(symbols))


def main() -> None:
    init_db()
    symbols = fetch_sp500_symbols()
    cache = Cache()
    cache.set("universe:sp500", {"symbols": symbols}, ttl_seconds=86400 * 7)
    print(f"Seeded {len(symbols)} S&P 500 symbols")


if __name__ == "__main__":
    main()
