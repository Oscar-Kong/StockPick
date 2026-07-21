"""Ticker universes for each screening bucket.

Discovery seeds (curated thematic lists) are merged with the official listing
master when available. Price, liquidity, and bucket-specific filters remain in
the scanner layer.
"""
from __future__ import annotations

import hashlib
import logging
from collections import defaultdict
from functools import lru_cache
from typing import Iterable

logger = logging.getLogger(__name__)

# --- Symbol normalization and exclusions ---

TICKER_ALIASES: dict[str, str] = {
    "SQ": "XYZ",
    "FREY": "TE",
    "SPACEX": "SPCX",
}

STALE_OR_DELISTED: set[str] = {
    "AREC",
    "ARVL",
    "ASTR",
    "AVXL",
    "AZIO",
    "BBBY",
    "BLDE",
    "BLNK",
    "BLUE",
    "BRR",
    "BYND",
    "CAN",
    "DADA",
    "DCFC",
    "FFAI",
    "FFIE",
    "FSR",
    "GFAI",
    "GOEV",
    "GOGL",
    "GOSS",
    "GRCL",
    "GREE",
    "HRTX",
    "HYFM",
    "IEP",
    "ILLR",
    "INVZ",
    "INZY",
    "ITOS",
    "KALV",
    "KNDI",
    "LAZR",
    "LBPH",
    "LEV",
    "LHAI",
    "LLAP",
    "LTHM",
    "MARK",
    "MAXN",
    "MFIC",
    "ML",
    "MULN",
    "NEP",
    "NKLA",
    "NM",
    "NOVA",
    "OCCI",
    "OXLC",
    "OXSQ",
    "PSEC",
    "PTRA",
    "QD",
    "RIDE",
    "RR",
    "SAVA",
    "SCVL",
    "SEM",
    "SKLZ",
    "SNAL",
    "TCPC",
    "VERV",
    "VORB",
    "WIRE",
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
    "ACB", "AMC", "BB", "CGC", "CLOV", "CRON", "GME", "GRWG", "HOOD", "IMPP",
    "NOK", "NVAX", "OGI", "SNDL", "SOFI", "SPCE", "TLRY", "WKHS",
]
_PENNY_CRYPTO = [
    "ABTC", "APLD", "ARBK", "BKKT", "BTBT", "BTCS", "BTDR", "CIFR", "CLSK", "CORZ",
    "DGXX", "EXOD", "GLXY", "HGBL", "HIVE", "HUT", "IREN", "MARA", "MSTR", "RIOT",
    "WULF",
]
_PENNY_EV_BATTERY = [
    "AMPX", "ATLX", "CENN", "CHPT", "ENVX", "EVEX", "EVGO", "GGR", "HYLN", "LCID",
    "LI", "MVST", "NIO", "NUVB", "OUST", "PSNY", "QS", "RIVN", "SES", "SLDP",
    "STEM", "VFS", "WBX", "XPEV", "ZVIA",
]
_PENNY_HYDROGEN_CLEAN = [
    "ARRY", "BE", "BLDP", "CLNE", "CSIQ", "DQ", "FCEL", "FLNC", "GPRE", "JKS",
    "MNTK", "PCT", "PLUG", "SHLS",
]
_PENNY_BATTERY_MATERIALS = [
    "ABAT", "ALB", "BEEM", "EOSE", "FAC", "LAC", "MP", "SEV", "TE",
]
_PENNY_EVTOL_AUTONOMY = [
    "ACHR", "AUR", "EH", "EVTL", "JOBY",
]
_PENNY_QUANTUM_AI = [
    "AEYE", "AI", "AISP", "AMBA", "APLD", "ARQQ", "BBAI", "BNAI", "DUOT", "IONQ",
    "LTRX", "NBIS", "ONDS", "PATH", "PERF", "PRCT", "QBTS", "QUBT", "RGTI", "SERV",
    "SOUN", "SSTI", "TEM", "VERI",
]
_PENNY_BIOTECH = [
    "ABEO", "ABOS", "ABSI", "ABUS", "ACAD", "ACH", "ACHV", "ACRS", "ACRV", "ADMA",
    "ADPT", "AGEN", "AIRS", "AKBA", "ALDX", "ALEC", "ALLO", "ALT", "ALXO", "ANAB",
    "ANIX", "ANNX", "ANVS", "APGE", "AQST", "ARCT", "ARDX", "ARMP", "ARTV", "ARVN",
    "ATAI", "ATEC", "AURA", "AUTL", "AVR", "BBOT", "BCRX", "BCYC", "BDTX", "BEAM",
    "BFLY", "BHVN", "BMEA", "BTMD", "CABA", "CADL", "CAPR", "CATX", "CCCC", "CGEM",
    "CHRS", "CING", "CLDX", "CMPS", "CMPX", "CNTN", "COGT", "COYA", "CRBU", "CRMD",
    "CRNX", "CRSP", "CRVO", "CRVS", "CTKB", "CTMX", "CVM", "CVRX", "CYTK", "DMAC",
    "DNA", "DNLI", "DTIL", "EBS", "EDIT", "EIKN", "ELDN", "ELTX", "EMBC", "EOLS",
    "EQ", "ERAS", "ESTA", "FATE", "FBIO", "FHTX", "FLNA", "FULC", "GALT", "GANX",
    "GERN", "GLUE", "GNLX", "HURA", "HYPD", "IBIO", "IBRX", "IKT", "IMRX", "IMUX",
    "IMVT", "INBX", "INDV", "INMB", "INO", "IOVA", "IPSC", "IRD", "IRON", "IRWD",
    "JANX", "KURA", "KYMR", "KYTX", "LCTX", "LEGN", "LENZ", "LFMD", "LRMR", "LTRN",
    "LXEO", "LXRX", "MDAI", "MDXG", "MGNX", "MNKD", "MRVI", "MXCT", "MYGN", "MYO",
    "NAGE", "NKTR", "NKTX", "NMAD", "NMRA", "NNVC", "NRXP", "NTLA", "NUS", "NXTC",
    "OABI", "OCGN", "OCUL", "OMER", "OPK", "ORGO", "OSUR", "OTLK", "OVID", "PACB",
    "PALI", "PBYI", "PEPG", "PGEN", "PLRX", "PRLD", "PRME", "PROK", "PRTA", "PYXS",
    "QCLS", "RCKT", "REPL", "RLMD", "RXRX", "RXST", "RZLT", "SABS", "SANA", "SENS",
    "SGMT", "SIGA", "SLDB", "SNWV", "SPRO", "SPRY", "STIM", "STTK", "STXS", "SVRA",
    "TALK", "TARA", "TGTX", "TOI", "TRDA", "TSHA", "TVRD", "TWST", "UNCY", "UPB",
    "VIR", "VNDA", "VSTM", "VYGR", "WHWK", "XERS", "XFOR", "ZNTL",
]
_PENNY_FINTECH = [
    "AFRM", "AGNT", "AHRT", "BBDC", "BILL", "BRBS", "BTGO", "BULL", "BZAI", "CFFN",
    "CION", "CMTG", "DAVE", "DFDV", "DOUG", "ECC", "FOUR", "FSCO", "GDOT", "GEMI",
    "GSBD", "HRZN", "INV", "KRNY", "LDI", "LMND", "LPRO", "LU", "MBI", "NAVI",
    "NCNO", "NMFC", "NRDS", "OPEN", "OPFI", "OPRT", "OSG", "OWL", "PAYO", "PFLT",
    "PNBK", "PNNT", "PURR", "PYPL", "RDZN", "RILY", "RKT", "RPC", "RWAY", "TOST",
    "UPST", "USDE", "UWMC", "WLTH", "XYZ", "ZSQR",
]
_PENNY_SPACE_DEFENSE = [
    "ASTS", "BAER", "BBAI", "BKSY", "KULR", "LUNR", "MNTS", "PL", "RDW", "RKLB",
    "SATL", "SIDU", "SPCE", "SPIR",
]
_PENNY_DRONE_DEFENSE = [
    "KTOS", "RCAT",
]
_PENNY_NUCLEAR = [
    "ASPI", "CCJ", "DNN", "EU", "LEU", "LTBR", "NNE", "NXE", "OKLO", "SMR",
    "UAMY", "UEC", "URG", "UROY", "UUUU",
]
_PENNY_MINING_METALS = [
    "AG", "ASM", "CDE", "CLF", "DC", "EQX", "EXK", "FNV", "FSM", "GORO",
    "GSM", "HL", "JELD", "KGC", "KRO", "MATV", "MUX", "NB", "NG", "NUCL",
    "PZG", "RGLD", "RYAM", "SLI", "SSRM", "SVM", "USAU", "VGZ", "WPM",
]
_PENNY_SHIPPING = [
    "BORR", "CMRE", "DAC", "ESEA", "GNK", "GSL", "HSHP", "PANL", "SBLK", "SFL",
    "STNG", "TNK", "TRMD", "ZIM",
]
_PENNY_CHINA_EMERGING = [
    "BILI", "BZ", "DOYU", "EDU", "FENG", "FINV", "FUTU", "GDS", "GOTU", "HUYA",
    "IQ", "KC", "LX", "MOMO", "NIU", "TAL", "TIGR", "TME", "TUYA", "VNET",
    "WB", "XNET", "YALA", "YMM", "ZH",
]
_PENNY_SEMI_HARDWARE = [
    "AAOI", "AEHR", "ALGM", "AMKR", "CAMT", "CEVA", "CRDO", "DIOD", "FORM", "GCTS",
    "HIMX", "IMOS", "INDI", "KN", "LAES", "LIDR", "LSCC", "MCHP", "MTSI", "MXL",
    "NVTS", "PI", "POET", "RMBS", "SITM", "SKYT", "SLAB", "VICR", "WOLF",
]
_PENNY_HEALTHCARE_SERVICES = [
    "ACHC", "ADUS", "ALHC", "AVAH", "BFAM", "BTSG", "CHE", "CNC", "CON", "CYH",
    "DGX", "ENSG", "HCA", "HIMS", "LH", "MOH", "OMCL", "OPCH", "OSCR", "PNTG",
    "PRGO", "TDOC",
]
_PENNY_CONSUMER_MEDIA = [
    "ANGI", "BMBL", "CARG", "CHWY", "CVNA", "CZR", "DASH", "DKNG", "ETSY", "EXPE",
    "FUBO", "GBTG", "GRAB", "IHRT", "LVS", "LYFT", "MGM", "MTCH", "NCMI", "PENN",
    "PINS", "RBLX", "REAL", "ROKU", "SE", "SIRI", "SNAP", "SPWH", "TRIP", "U",
    "W", "WYNN",
]
_PENNY_INDUSTRIAL_MISC = [
    "AIRJ", "AIRO", "ALTO", "AMTX", "APPS", "ASO", "AWI", "BLDR", "BOOT", "BTX",
    "BYRN", "CAL", "CBUS", "CDXS", "COLM", "CWH", "DFLI", "DKS", "DOV", "EMPD",
    "FF", "FLS", "FWDI", "GEVO", "GFF", "GIII", "GNRC", "GTES", "GTN", "GVA",
    "HOG", "HOVR", "IMSR", "IR", "JBI", "KTB", "LASE", "LODE", "LWLG", "MASS",
    "MBUU", "MLI", "MTW", "MYRG", "NAUT", "NEOV", "NMAX", "NNBR", "NRGV", "NWL",
    "PNR", "POWW", "PRIM", "PSKY", "QTRX", "ROAD", "ROCK", "SKYQ", "SMID", "SND",
    "SSP", "STRL", "SWIM", "SXC", "TEX", "TGLS", "THO", "TILE", "TLYS", "TPC",
    "TROX", "TRUP", "TT", "TTC", "TWI", "UA", "VYX", "WGO", "WRAP", "ZUMZ",
]
_PENNY_SOFTWARE_CLOUD = [
    "ALOY", "AMPL", "ASAN", "ASTI", "ATOM", "BLND", "CAST", "CCC", "CERS", "CERT",
    "CMRC", "CMTL", "COUR", "CRCT", "CRNC", "CRSR", "CXM", "DDD", "DJT", "DOMO",
    "DXC", "ERII", "EVLV", "EXFY", "GDRX", "GDYN", "GLOO", "GSIT", "GTM", "HCAT",
    "IDN", "IMMR", "KDK", "KLTR", "KOPN", "KVHI", "LAW", "LZ", "MOBX", "MRLN",
    "NABL", "NIXX", "NXDR", "OPTX", "PAYS", "PDYN", "QMCO", "RBBN", "RUM", "RXT",
    "SABR", "SBET", "SLNH", "SPT", "SST", "SSTK", "SSYS", "SVCO", "TASK", "TLS",
    "TYGO", "UIS", "UPWK", "VTIX", "VUZI", "VWAV", "WEAV", "XPER", "XRX", "XTIA",
    "YEXT", "ZIP",
]
_PENNY_TELECOM_CONNECTIVITY = [
    "AIOT", "AMPG", "BWEN", "CXDO", "INSG", "KSCP", "LILA", "LILAK", "LUMN",
]
_PENNY_ENERGY_OIL_GAS = [
    "ACDC", "AMPY", "ANNA", "BATL", "BSIN", "EAF", "EGY", "FIP", "GLND", "GRNT",
    "HLX", "HPK", "KLXE", "NPWR", "NUAI", "PTEN", "REI", "RES", "SOC", "TTI",
    "WTI",
]
_PENNY_REAL_ESTATE = [
    "ABR", "ACRE", "ADAM", "AIV", "ARI", "BDN", "BHR", "BRSP", "DHC", "EARN",
    "ELME", "ESRT", "FBRT", "FPI", "FRMI", "GNL", "GPMT", "ILPT", "INN", "IVR",
    "KREF", "LAND", "MFA", "MPT", "ORC", "PDM", "RC", "RITM", "RWT", "SEVN",
    "SITC", "SVC", "TRTX",
]
_PENNY_CONSUMER_RETAIL = [
    "ACCO", "ACVA", "ADT", "AMCI", "ANGX", "ARHS", "ASLE", "ASPN", "BIRD", "BLMN",
    "BRCB", "BZFD", "CCO", "CNDT", "COTY", "CPSH", "CRMT", "CURI", "CURV", "DBI",
    "DCH", "DTI", "EVH", "FJET", "FNKO", "FOSL", "GOGO", "GT", "HDSN", "HLLY",
    "HLMN", "HNST", "HODO", "HTZ", "INUV", "JBLU", "KLC", "KODK", "LESL", "MBC",
    "MNTN", "NTRP", "OI", "OIS", "OPRX", "PACK", "PAL", "PLBY", "PRTH", "PTLO",
    "PTON", "PUSA", "RGP", "RPAY", "SFIX", "SG", "SKYX", "SRTA", "STUB", "SVV",
    "TBI", "TDAY", "TDUP", "THRY", "TIC", "TRON", "TSSI", "TTEC", "UAA", "ULCC",
    "VENU", "VRRM", "WALD", "WEN", "WOOF", "WU", "XMAX", "XPOF",
]
_PENNY_CONSUMER_STAPLES = [
    "ARKO", "BGS", "BRCC", "DNUT", "FLO", "GO", "SUJA", "UTZ", "WEST",
]
_PENNY_UTILITIES_POWER = [
    "AQN", "CDZI", "GFUZ", "NEXT", "OPAL",
]
_PENNY_HEALTHCARE_MEDTECH = [
    "LUCD", "MODD", "RCEL", "TMCI", "VANI",
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
    "software_cloud": _PENNY_SOFTWARE_CLOUD,
    "telecom_connectivity": _PENNY_TELECOM_CONNECTIVITY,
    "energy_oil_gas": _PENNY_ENERGY_OIL_GAS,
    "real_estate": _PENNY_REAL_ESTATE,
    "consumer_retail": _PENNY_CONSUMER_RETAIL,
    "consumer_staples": _PENNY_CONSUMER_STAPLES,
    "utilities_power": _PENNY_UTILITIES_POWER,
    "healthcare_medtech": _PENNY_HEALTHCARE_MEDTECH,
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
    {
        sym
        for group in _THEME_GROUPS.values()
        for raw in group
        for sym in (normalize_symbol(raw),)
        if sym and sym not in STALE_OR_DELISTED and sym not in SECTOR_ETFS
    }
)

# Backward-compatible alias — prefer PENNY_DISCOVERY_SEEDS in new code.
PENNY_CANDIDATES = PENNY_DISCOVERY_SEEDS

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


def cap_universe_for_scan(
    symbols: list[str],
    limit: int,
    *,
    revision: str = "",
) -> list[str]:
    """Return at most ``limit`` symbols without alphabetical-prefix bias.

    When ``limit`` is <= 0 or >= len(symbols), return a copy of ``symbols``.
    Selection is deterministic for a given (symbols, limit, revision) so scans
    stay reproducible within a listing-master revision.
    """
    if limit <= 0 or limit >= len(symbols):
        return list(symbols)

    def _rank(sym: str) -> str:
        return hashlib.sha256(f"{revision}:{sym}".encode()).hexdigest()

    selected = sorted(symbols, key=_rank)[:limit]
    return sorted(selected)


def get_universe(bucket: str) -> list[str]:
    """Return sorted unique tickers for a scan bucket."""
    from core.sleeve import normalize_sleeve

    bucket = normalize_sleeve(bucket)
    revision = get_universe_revision()
    return list(_get_universe_cached(bucket, revision))
