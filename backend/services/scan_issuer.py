"""Map tickers to issuer keys — dedupe share classes in scan output."""
from __future__ import annotations

import re

from data.universe import normalize_symbol

# Known multi-class listings → single issuer id (uppercase).
_ISSUER_BY_SYMBOL: dict[str, str] = {
    "GOOG": "ALPHABET",
    "GOOGL": "ALPHABET",
    "BRK-A": "BERKSHIRE",
    "BRK-B": "BERKSHIRE",
    "FOX": "FOX_CORP",
    "FOXA": "FOX_CORP",
    "NWS": "NEWS_CORP",
    "NWSA": "NEWS_CORP",
    "UA": "UNDER_ARMOUR",
    "UAA": "UNDER_ARMOUR",
    "LEN": "LENNAR",
    "LEN-B": "LENNAR",
    "HEI": "HEICO",
    "HEI-A": "HEICO",
    "BF-A": "BROWN_FORMAN",
    "BF-B": "BROWN_FORMAN",
}


def issuer_key(symbol: str, info: dict | None = None) -> str:
    """Stable issuer identifier for diversification (not necessarily CIK)."""
    sym = normalize_symbol(symbol)
    if sym in _ISSUER_BY_SYMBOL:
        return _ISSUER_BY_SYMBOL[sym]

    info = info or {}
    cik = info.get("cik") or info.get("companyId")
    if cik:
        return f"CIK_{str(cik).strip()}"

    name = (info.get("shortName") or info.get("longName") or "").upper()
    name = re.sub(r"\s+(INC|CORP|LTD|PLC|CLASS [A-Z]).*$", "", name).strip()
    if name:
        slug = re.sub(r"[^A-Z0-9]+", "_", name).strip("_")
        if slug:
            return slug[:48]

    base = re.sub(r"-[A-Z]$", "", sym)
    return base or sym
