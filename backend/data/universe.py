"""Ticker universes for each screening bucket."""
from functools import lru_cache

# Curated US equities — expand over time or load from CSV
SP500_SAMPLE = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "BRK-B", "UNH", "JNJ",
    "V", "XOM", "JPM", "WMT", "MA", "PG", "HD", "CVX", "MRK", "ABBV",
    "KO", "PEP", "COST", "AVGO", "LLY", "TMO", "MCD", "CSCO", "ACN", "ABT",
    "DHR", "NEE", "TXN", "LIN", "PM", "UNP", "RTX", "HON", "QCOM", "LOW",
    "INTU", "SPGI", "AMAT", "IBM", "GE", "CAT", "DE", "AXP", "GS", "MS",
    "BLK", "SYK", "ADP", "GILD", "MDT", "VRTX", "REGN", "ISRG", "BKNG", "ADI",
    "PANW", "SNPS", "CDNS", "KLAC", "MU", "LRCX", "AMGN", "CI", "ELV", "ZTS",
    "CMCSA", "NFLX", "DIS", "TMUS", "VZ", "T", "ORCL", "CRM", "NOW", "ADBE",
    "PYPL", "SQ", "SHOP", "UBER", "ABNB", "COIN", "PLTR", "SOFI", "RIVN", "LCID",
    "F", "GM", "DAL", "UAL", "AAL", "CCL", "NCLH", "MAR", "HLT", "SBUX",
    "NKE", "LULU", "ROST", "TJX", "DG", "DLTR", "KR", "WBA", "CVS", "MO",
    "PM", "BTI", "CL", "KMB", "CHD", "CLX", "HSY", "K", "GIS", "SJM",
    "AMD", "INTC", "QCOM", "ON", "MRVL", "SWKS", "MPWR", "ENPH", "FSLR", "RUN",
    "XLE", "XLF", "XLK", "XLV", "XLI", "XLP", "XLY", "XLB", "XLU", "XLRE",
]

PENNY_CANDIDATES = [
    "SNDL", "NIO", "PLUG", "FCEL", "BB", "NOK", "AMC", "GME", "CLOV", "WISH",
    "SPCE", "TLRY", "CGC", "ACB", "HEXO", "MULN", "GOEV", "WKHS", "RIDE", "NKLA",
    "FFIE", "MARA", "RIOT", "HUT", "BITF", "CLSK", "HIVE", "CAN", "SOS", "EBON",
    "SIRI", "FUBO", "SKLZ", "OPEN", "RDFN", "UWMC", "RKT", "AFRM", "UPST", "HOOD",
    "PATH", "AI", "BBAI", "SOUN", "IONQ", "RGTI", "QBTS", "LAZR", "VLDR", "OUST",
    "LCID", "RIVN", "FSR", "CHPT", "BLNK", "EVGO", "QS", "MVST", "ENVX", "STEM",
    "DNA", "PACB", "CRSP", "EDIT", "NTLA", "BEAM", "VERV", "RXRX", "TWST", "BE",
]

MEDIUM_CANDIDATES = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "AMD", "INTC", "QCOM",
    "CRM", "NOW", "ADBE", "ORCL", "PANW", "SNPS", "CDNS", "CRWD", "ZS", "DDOG",
    "NET", "SNOW", "MDB", "TEAM", "SHOP", "SQ", "PYPL", "UBER", "ABNB", "DASH",
    "ROKU", "PINS", "SNAP", "TTD", "RBLX", "U", "DKNG", "PENN", "MGM", "WYNN",
    "LVS", "CZR", "MAR", "HLT", "H", "EXPE", "BKNG", "ABNB", "DAL", "UAL",
    "LUV", "AAL", "JBLU", "ALK", "HA", "SAVE", "FDX", "UPS", "XPO", "ODFL",
    "DE", "CAT", "EMR", "ETN", "ROK", "PH", "ITW", "CMI", "PCAR", "URI",
    "COST", "WMT", "TGT", "HD", "LOW", "DG", "DLTR", "ROST", "TJX", "BBY",
    "NKE", "LULU", "DECK", "ONON", "SKX", "UAA", "VFC", "PVH", "RL", "TPR",
]

COMPOUNDER_CANDIDATES = [
    "COST", "MSFT", "AAPL", "GOOGL", "V", "MA", "UNH", "JNJ", "PG", "KO",
    "PEP", "HD", "LOW", "MCD", "SBUX", "NKE", "TMO", "ABT", "DHR", "SYK",
    "ISRG", "INTU", "ADP", "SPGI", "BLK", "BRK-B", "JPM", "AXP", "VRTX", "REGN",
    "LLY", "AMGN", "GILD", "BMY", "MRK", "ABBV", "ZTS", "IDXX", "EW", "BDX",
    "NEE", "DUK", "SO", "AEP", "XEL", "WEC", "ES", "ED", "AWK", "ATO",
    "LIN", "APD", "ECL", "SHW", "ITW", "EMR", "ROK", "HON", "GE", "CAT",
    "UNP", "CSX", "NSC", "WM", "RSG", "FAST", "CTAS", "ROL", "POOL", "WSM",
    "ORLY", "AZO", "AAP", "TSCO", "DG", "WMT", "COST", "KR", "SYY", "USFD",
]


def _load_sp500_from_cache() -> list[str]:
    try:
        from data.cache import Cache

        data = Cache().get("universe:sp500")
        if data and data.get("symbols"):
            return data["symbols"]
    except Exception:
        pass
    return []


@lru_cache(maxsize=4)
def get_universe(bucket: str) -> list[str]:
    sp500 = _load_sp500_from_cache()
    if bucket == "penny":
        base = PENNY_CANDIDATES
    elif bucket == "medium":
        base = MEDIUM_CANDIDATES + SP500_SAMPLE
        if sp500:
            base = base + sp500
    elif bucket == "compounder":
        base = COMPOUNDER_CANDIDATES
        if sp500:
            base = base + sp500
    else:
        base = SP500_SAMPLE
    return sorted(set(base))
