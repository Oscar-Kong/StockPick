"""Map GICS-style sectors to sector ETFs for relative strength."""
SECTOR_TO_ETF: dict[str, str] = {
    "Technology": "XLK",
    "Healthcare": "XLV",
    "Financial Services": "XLF",
    "Financial": "XLF",
    "Consumer Cyclical": "XLY",
    "Consumer Defensive": "XLP",
    "Energy": "XLE",
    "Industrials": "XLI",
    "Basic Materials": "XLB",
    "Materials": "XLB",
    "Real Estate": "XLRE",
    "Utilities": "XLU",
    "Communication Services": "XLC",
    "Telecommunication Services": "XLC",
}


def sector_etf(sector: str | None) -> str | None:
    if not sector:
        return None
    if sector in SECTOR_TO_ETF:
        return SECTOR_TO_ETF[sector]
    for key, etf in SECTOR_TO_ETF.items():
        if key.lower() in sector.lower():
            return etf
    return None
