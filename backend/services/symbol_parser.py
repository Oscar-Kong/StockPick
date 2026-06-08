"""Parse ticker symbols from free-form user input."""
from __future__ import annotations

import re

# e.g. AAPL, BRK-B, BRK.B
_TICKER_RE = re.compile(r"^[A-Z]{1,5}([.-][A-Z])?$")


def parse_symbols(text: str) -> list[str]:
    if not text or not text.strip():
        return []

    raw = re.split(r"[\s,;|\n\t]+", text.strip().upper())
    seen: set[str] = set()
    symbols: list[str] = []

    for part in raw:
        token = part.strip().lstrip("$").rstrip(".")
        if not token:
            continue
        # Normalize Yahoo-style BRK.B -> BRK-B
        token = token.replace(".", "-")
        if not _TICKER_RE.match(token):
            continue
        if token in seen:
            continue
        seen.add(token)
        symbols.append(token)

    return symbols
