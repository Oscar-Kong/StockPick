from data.cache import get_active_quote_snapshot, save_active_quote_snapshot


def test_rotating_quote_passes_merge_per_symbol_and_prune_closed_symbols():
    save_active_quote_snapshot(
        {"ONE": 1.0},
        as_of="2026-08-16T14:30:00Z",
        active_symbols=["ONE", "TWO"],
    )
    save_active_quote_snapshot(
        {"TWO": 2.0},
        as_of="2026-08-16T14:31:00Z",
        active_symbols=["ONE", "TWO"],
    )

    snapshot = get_active_quote_snapshot()
    assert snapshot["quotes"]["ONE"]["as_of"] == "2026-08-16T14:30:00Z"
    assert snapshot["quotes"]["TWO"]["as_of"] == "2026-08-16T14:31:00Z"

    save_active_quote_snapshot({}, as_of="2026-08-16T14:32:00Z", active_symbols=["TWO"])
    assert set(get_active_quote_snapshot()["quotes"]) == {"TWO"}
