"""Ticker universes for each screening bucket.

Discovery seeds (curated thematic lists) are merged with the official listing
master when available. Price, liquidity, and bucket-specific filters remain in
the scanner layer.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from functools import lru_cache
from typing import Iterable

logger = logging.getLogger(__name__)

# --- Symbol normalization and exclusions ---

TICKER_ALIASES: dict[str, str] = {
    "SQ": "XYZ",
    "FREY": "TE",
}

STALE_OR_DELISTED: set[str] = {
    "GOEV",
    "NKLA",
    "PTRA",
    "FSR",
    "RIDE",
    "ARVL",
    "VORB",
    "LLAP",
    "ASTR",
    "LTHM",
    "GRCL",
    "MAXN",
    "FFIE",
    "DCFC",
    "MULN",
    "BLUE",
    "NOVA",
    "BLDE",
}

SECTOR_ETFS: set[str] = {
    "XLE",
    "XLF",
    "XLK",
    "XLV",
    "XLI",
    "XLP",
    "XLY",
    "XLB",
    "XLU",
    "XLRE",
}


def normalize_symbol(symbol: str) -> str:
    """Return canonical ticker: trimmed, uppercased, aliased, class-share dash form."""
    sym = (symbol or "").strip().upper()
    if not sym:
        return ""
    sym = sym.replace(".", "-")
    return TICKER_ALIASES.get(sym, sym)


# --- Large-cap discovery seeds (not official S&P 500 membership) ---

LARGE_CAP_SEEDS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "BRK-B", "UNH", "JNJ",
    "V", "XOM", "JPM", "WMT", "MA", "PG", "HD", "CVX", "MRK", "ABBV",
    "KO", "PEP", "COST", "AVGO", "LLY", "TMO", "MCD", "CSCO", "ACN", "ABT",
    "DHR", "NEE", "TXN", "LIN", "PM", "UNP", "RTX", "HON", "QCOM", "LOW",
    "INTU", "SPGI", "AMAT", "IBM", "GE", "CAT", "DE", "AXP", "GS", "MS",
    "BLK", "SYK", "ADP", "GILD", "MDT", "VRTX", "REGN", "ISRG", "BKNG", "ADI",
    "PANW", "SNPS", "CDNS", "KLAC", "MU", "LRCX", "AMGN", "CI", "ELV", "ZTS",
    "CMCSA", "NFLX", "DIS", "TMUS", "VZ", "T", "ORCL", "CRM", "NOW", "ADBE",
    "PYPL", "XYZ", "SHOP", "UBER", "ABNB", "COIN", "PLTR", "SOFI", "RIVN", "LCID",
    "F", "GM", "DAL", "UAL", "AAL", "CCL", "NCLH", "MAR", "HLT", "SBUX",
    "NKE", "LULU", "ROST", "TJX", "DG", "DLTR", "KR", "CVS", "MO",
    "BTI", "CL", "KMB", "CHD", "CLX", "HSY", "GIS", "SJM",
    "AMD", "INTC", "ON", "MRVL", "SWKS", "MPWR", "ENPH", "FSLR", "RUN",
]

# Backward-compatible alias — prefer LARGE_CAP_SEEDS in new code.
SP500_SAMPLE = LARGE_CAP_SEEDS

# --- Penny bucket discovery seeds (thematic; not guaranteed sub-$5) ---

_PENNY_MEME_RETAIL = [
    "SNDL", "AMC", "GME", "BB", "NOK", "CLOV", "SPCE", "HOOD", "SOFI", "BYND",
    "TLRY", "CGC", "ACB", "CRON", "OGI", "GRWG", "HYFM", "IMPP", "NVAX", "WKHS",
]

_PENNY_CRYPTO = [
    "MARA", "RIOT", "HUT", "CLSK", "HIVE", "CAN", "BTBT", "ARBK", "WULF",
    "CORZ", "IREN", "CIFR", "BTCS", "EXOD", "HGBL", "BKKT", "DGXX", "MSTR",
    "GLXY", "BTDR", "APLD",
]

_PENNY_EV_BATTERY = [
    "NIO", "LCID", "RIVN", "CHPT", "BLNK", "EVGO", "QS", "MVST", "ENVX", "STEM",
    "LAZR", "OUST", "PSNY", "HYLN", "XPEV", "LI", "VFS", "KNDI",
    "FFAI", "LEV", "GGR", "CENN", "EVEX", "ZVIA", "AMPX",
    "WBX", "NUVB", "SES", "SLDP",
]

_PENNY_HYDROGEN_CLEAN = [
    "PLUG", "FCEL", "BE", "BLDP", "GPRE", "ARRY", "SHLS", "CSIQ", "JKS",
    "DQ", "FLNC", "NEP", "PCT",
]

_PENNY_BATTERY_MATERIALS = [
    "LAC", "MP", "ALB", "EOSE", "BEEM", "FAC", "SEV", "TE",
]

_PENNY_EVTOL_AUTONOMY = [
    "JOBY", "ACHR", "EH", "EVTL",
]

_PENNY_QUANTUM_AI = [
    "IONQ", "RGTI", "QBTS", "SOUN", "BBAI", "AI", "PATH", "GFAI", "VERI", "MARK",
    "PRCT", "DUOT", "LTRX", "PERF", "AEYE", "AISP", "BNAI", "SSTI", "AMBA", "ONDS",
    "QUBT", "ARQQ", "NBIS", "TEM", "SERV", "APLD",
]

_PENNY_BIOTECH = [
    "DNA", "PACB", "CRSP", "EDIT", "NTLA", "BEAM", "VERV", "RXRX", "TWST", "SANA",
    "FATE", "AUTL", "ARCT", "IOVA", "NKTR", "SAVA", "TGTX", "VSTM", "ALLO",
    "BCYC", "ADPT", "KURA", "RCKT", "AGEN", "ALT", "ANAB", "ARVN", "ABUS", "ACAD",
    "ADMA", "ALXO", "APGE", "ARDX", "ATAI", "AVXL", "BCRX", "BHVN",
    "BMEA", "CAPR", "CCCC", "CGEM", "CLDX", "CMPS", "COGT", "CRBU", "CRNX",
    "CRVS", "CTMX", "CTKB", "CYTK", "DNLI", "ERAS", "ESTA", "FULC",
    "GERN", "GLUE", "GNLX", "GOSS", "HRTX", "IMVT", "IMUX", "INBX",
    "INDV", "INZY", "IRON", "ITOS", "JANX", "KALV", "KYMR", "LBPH", "LEGN", "LRMR",
]

_PENNY_FINTECH = [
    "AFRM", "UPST", "OPEN", "UWMC", "RKT", "LMND", "OPFI", "PAYO", "NRDS", "LU",
    "DAVE", "FOUR", "GDOT", "NCNO", "TOST", "BILL", "XYZ", "PYPL", "BULL", "ML",
]

_PENNY_SPACE_DEFENSE = [
    "RKLB", "LUNR", "RDW", "MNTS", "SPIR", "BKSY", "PL", "ASTS", "SATL",
    "SIDU", "SPCE", "KULR", "BBAI",
]

_PENNY_DRONE_DEFENSE = [
    "RCAT", "KTOS",
]

_PENNY_NUCLEAR = [
    "UEC", "DNN", "URG", "UAMY", "UUUU", "LEU", "EU", "NXE", "UROY", "CCJ",
    "SMR", "OKLO", "NNE", "LTBR", "ASPI",
]

_PENNY_MINING_METALS = [
    "USAU", "GORO", "MUX", "EXK", "SLI", "HL", "AG", "CDE", "NG", "GSM",
    "SVM", "ASM", "FSM", "EQX", "KGC", "SSRM", "WPM", "RGLD", "FNV",
]

_PENNY_SHIPPING = [
    "ZIM", "SBLK", "GOGL", "NM", "DAC", "GSL", "CMRE", "STNG", "TNK",
    "ESEA", "SFL", "GNK", "HSHP", "TRMD", "PANL", "BORR",
]

_PENNY_CHINA_EMERGING = [
    "FUTU", "TIGR", "VNET", "IQ", "BILI", "TAL", "EDU", "GOTU", "GDS", "KC",
    "TUYA", "ZH", "MOMO", "WB", "HUYA", "DOYU", "YMM", "BZ", "FINV",
    "QD", "TME", "YALA", "LX", "DADA", "FENG", "NIU", "XNET",
]

_PENNY_SEMI_HARDWARE = [
    "WOLF", "ALGM", "SKYT", "POET", "AAOI", "CRDO", "NVTS", "INDI", "LAES", "LIDR",
    "INVZ", "AEHR", "AMKR", "FORM", "KN", "MXL", "PI", "RMBS", "SITM", "SLAB",
    "VICR", "CAMT", "CEVA", "DIOD", "HIMX", "IMOS", "LSCC", "MCHP", "MTSI",
]

_PENNY_HEALTHCARE_SERVICES = [
    "HIMS", "OSCR", "ALHC", "TDOC", "OMCL", "ACHC", "BFAM", "BTSG", "CNC",
    "ENSG", "MOH", "PNTG", "PRGO", "SEM", "ADUS",
    "AVAH", "CHE", "CON", "CYH", "DGX", "HCA", "LH", "OPCH",
]

_PENNY_CONSUMER_MEDIA = [
    "FUBO", "SKLZ", "SIRI", "ROKU", "PINS", "SNAP", "RBLX", "U", "DKNG", "PENN",
    "WYNN", "CZR", "MGM", "LVS", "CHWY", "ETSY", "W", "REAL", "CVNA", "CARG",
    "BMBL", "MTCH", "ANGI", "EXPE", "TRIP", "LYFT", "DASH", "GRAB", "SE",
]

_PENNY_INDUSTRIAL_MISC = [
    "TRUP", "ASO", "DKS", "CAL", "BOOT", "SCVL", "ZUMZ",
    "UA", "COLM", "GIII", "KTB", "TLYS", "THO", "WGO", "CWH", "MBUU", "HOG",
    "TILE", "TTC", "TEX", "MTW", "GNRC", "TT", "IR", "DOV", "PNR", "FLS",
    "GTES", "MLI", "WIRE", "ROAD", "MYRG", "PRIM", "STRL", "GVA", "TPC",
    "BLDR", "ROCK", "SMID", "TGLS", "AWI", "GFF",
]

_THEME_GROUPS: dict[str, list[str]] = {
    "meme_retail": _PENNY_MEME_RETAIL,
    "crypto": _PENNY_CRYPTO,
    "ev_battery": _PENNY_EV_BATTERY,
    "hydrogen_clean": _PENNY_HYDROGEN_CLEAN,
    "battery_materials": _PENNY_BATTERY_MATERIALS,
    "evtol_autonomy": _PENNY_EVTOL_AUTONOMY,
    "quantum_ai": _PENNY_QUANTUM_AI,
    "biotech": _PENNY_BIOTECH,
    "fintech": _PENNY_FINTECH,
    "space_defense": _PENNY_SPACE_DEFENSE,
    "drone_defense": _PENNY_DRONE_DEFENSE,
    "nuclear": _PENNY_NUCLEAR,
    "mining_metals": _PENNY_MINING_METALS,
    "shipping": _PENNY_SHIPPING,
    "china_emerging": _PENNY_CHINA_EMERGING,
    "semi_hardware": _PENNY_SEMI_HARDWARE,
    "healthcare_services": _PENNY_HEALTHCARE_SERVICES,
    "consumer_media": _PENNY_CONSUMER_MEDIA,
    "industrial_misc": _PENNY_INDUSTRIAL_MISC,
}


def _build_theme_membership() -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    theme_membership: dict[str, set[str]] = {}
    symbol_themes: dict[str, set[str]] = defaultdict(set)
    for theme, symbols in _THEME_GROUPS.items():
        normalized = {normalize_symbol(s) for s in symbols if normalize_symbol(s)}
        theme_membership[theme] = normalized
        for sym in normalized:
            symbol_themes[sym].add(theme)
    return theme_membership, dict(symbol_themes)


THEME_MEMBERSHIP, SYMBOL_THEMES = _build_theme_membership()

PENNY_DISCOVERY_SEEDS = sorted(
    {sym for group in _THEME_GROUPS.values() for sym in group}
)

# Backward-compatible alias — prefer PENNY_DISCOVERY_SEEDS in new code.
PENNY_CANDIDATES = PENNY_DISCOVERY_SEEDS

MEDIUM_CANDIDATES = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "AMD", "INTC", "QCOM",
    "CRM", "NOW", "ADBE", "ORCL", "PANW", "SNPS", "CDNS", "CRWD", "ZS", "DDOG",
    "NET", "SNOW", "MDB", "TEAM", "SHOP", "XYZ", "PYPL", "UBER", "ABNB", "DASH",
    "ROKU", "PINS", "SNAP", "TTD", "RBLX", "U", "DKNG", "PENN", "MGM", "WYNN",
    "LVS", "CZR", "MAR", "HLT", "H", "EXPE", "BKNG", "DAL", "UAL",
    "LUV", "AAL", "JBLU", "ALK", "FDX", "UPS", "XPO", "ODFL", "JBHT", "CHRW",
    "DE", "CAT", "EMR", "ETN", "ROK", "PH", "ITW", "CMI", "PCAR", "URI",
    "COST", "WMT", "TGT", "HD", "LOW", "DG", "DLTR", "ROST", "TJX", "BBY",
    "NKE", "LULU", "DECK", "ONON", "SKX", "UAA", "VFC", "PVH", "RL", "TPR",
    "PLTR", "SOFI", "HOOD", "COIN", "MSTR", "SMCI", "ARM", "AVGO", "MU", "LRCX",
    "KLAC", "AMAT", "MRVL", "ON", "SWKS", "MPWR", "ENPH", "FSLR", "CEG", "VST",
]

COMPOUNDER_CANDIDATES = [
    "COST", "MSFT", "AAPL", "GOOGL", "V", "MA", "UNH", "JNJ", "PG", "KO",
    "PEP", "HD", "LOW", "MCD", "SBUX", "NKE", "TMO", "ABT", "DHR", "SYK",
    "ISRG", "INTU", "ADP", "SPGI", "BLK", "BRK-B", "JPM", "AXP", "VRTX", "REGN",
    "LLY", "AMGN", "GILD", "BMY", "MRK", "ABBV", "ZTS", "IDXX", "EW", "BDX",
    "NEE", "DUK", "SO", "AEP", "XEL", "WEC", "ES", "ED", "AWK", "ATO",
    "LIN", "APD", "ECL", "SHW", "ITW", "EMR", "ROK", "HON", "GE", "CAT",
    "UNP", "CSX", "NSC", "WM", "RSG", "FAST", "CTAS", "ROL", "POOL", "WSM",
    "ORLY", "AZO", "AAP", "TSCO", "DG", "WMT", "KR", "SYY", "USFD", "MNST",
    "CL", "KMB", "CHD", "CLX", "HSY", "GIS", "SJM", "CPB", "CAG",
    "VICI", "O", "PLD", "EQIX", "AMT", "CCI", "SBAC", "DLR", "PSA", "EXR",
]


def _load_sp500_from_cache() -> list[str]:
    try:
        from data.cache import Cache

        data = Cache().get("universe:sp500")
        if data and data.get("symbols"):
            return [normalize_symbol(s) for s in data["symbols"]]
    except Exception:
        pass
    return []


def get_universe_revision() -> str:
    try:
        from data.listing_master import get_listing_revision

        rev = get_listing_revision()
        if rev:
            return rev
    except Exception:
        pass
    sp500 = _load_sp500_from_cache()
    if sp500:
        return f"sp500-only-{len(sp500)}"
    return "curated-fallback"


def _filter_curated_symbols(symbols: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for raw in symbols:
        sym = normalize_symbol(raw)
        if not sym or sym in seen:
            continue
        if sym in STALE_OR_DELISTED or sym in SECTOR_ETFS:
            continue
        seen.add(sym)
        out.append(sym)
    return sorted(out)


def _validate_against_listings(symbols: Iterable[str], active: set[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for raw in symbols:
        sym = normalize_symbol(raw)
        if not sym or sym in seen:
            continue
        if sym in STALE_OR_DELISTED or sym in SECTOR_ETFS:
            continue
        if sym not in active:
            continue
        seen.add(sym)
        out.append(sym)
    return sorted(out)


def _resolve_bucket_seeds(bucket: str) -> list[str]:
    sp500 = _load_sp500_from_cache()
    if bucket == "penny":
        return list(PENNY_DISCOVERY_SEEDS)
    if bucket == "medium":
        base = MEDIUM_CANDIDATES + LARGE_CAP_SEEDS
        if sp500:
            base = base + sp500
        return base
    if bucket == "compounder":
        base = list(COMPOUNDER_CANDIDATES)
        if sp500:
            base = base + sp500
        return base
    return list(LARGE_CAP_SEEDS)


@lru_cache(maxsize=16)
def _get_universe_cached(bucket: str, revision: str) -> tuple[str, ...]:
    seeds = _resolve_bucket_seeds(bucket)
    active: set[str] | None = None
    try:
        from data.listing_master import get_active_listing_symbols

        active = get_active_listing_symbols()
    except Exception as exc:
        logger.debug("Listing master unavailable for universe build: %s", exc)

    if active is not None:
        validated = _validate_against_listings(seeds, active)
        if validated:
            return tuple(validated)
        logger.warning(
            "Listing intersection empty for bucket=%s; falling back to curated seeds",
            bucket,
        )

    logger.info(
        "Universe bucket=%s using curated fallback (listing validation unavailable)",
        bucket,
    )
    return tuple(_filter_curated_symbols(seeds))


def get_universe(bucket: str) -> list[str]:
    """Return sorted unique tickers for a scan bucket."""
    revision = get_universe_revision()
    return list(_get_universe_cached(bucket, revision))
