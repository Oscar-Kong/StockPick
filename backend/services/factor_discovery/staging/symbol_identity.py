"""Deterministic symbol identity normalization for staging."""
from __future__ import annotations

import hashlib
import re

SYMBOL_MAPPING_VERSION = "symbol_mapping_v1"
_SYMBOL_RE = re.compile(r"^[A-Z0-9.-]{1,16}$")


def normalize_symbol(symbol: str) -> str:
    sym = symbol.strip().upper().replace("/", "-")
    if "." in sym and "-" not in sym.split(".")[0]:
        # BRK.B -> BRK-B style for consistency
        parts = sym.split(".")
        if len(parts) == 2 and len(parts[1]) <= 2:
            sym = f"{parts[0]}-{parts[1]}"
    return sym


def validate_symbol(symbol: str) -> tuple[bool, str | None]:
    norm = normalize_symbol(symbol)
    if not _SYMBOL_RE.match(norm):
        return False, f"invalid_symbol:{symbol}"
    return True, None


def symbol_mapping_hash(symbols: list[str]) -> str:
    canonical = "|".join(sorted(normalize_symbol(s) for s in symbols))
    return f"sha256:{hashlib.sha256(canonical.encode()).hexdigest()[:16]}"
