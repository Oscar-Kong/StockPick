"""Load open portfolio holdings for impact calculations."""
from __future__ import annotations


def load_holdings(*, prefer_journal: bool = True) -> tuple[list[str], str]:
    """Return (symbols, source)."""
    if prefer_journal:
        try:
            from data.cache import list_trades

            trades = list_trades(limit=200)
            open_syms = {
                str(t.get("symbol", "")).upper()
                for t in trades
                if t.get("exit_time") is None and t.get("symbol")
            }
            if open_syms:
                return sorted(open_syms), "journal"
        except Exception:
            pass

    try:
        from data import cache as cache_module

        rows = cache_module.get_watchlist()
        syms = [str(r.get("symbol", "")).upper() for r in rows if r.get("symbol")]
        if syms:
            return syms[:12], "watchlist"
    except Exception:
        pass

    return [], "default"
