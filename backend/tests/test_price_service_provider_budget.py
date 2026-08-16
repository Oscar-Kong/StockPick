from __future__ import annotations

from unittest.mock import MagicMock

import pandas as pd

from data.price_service import PriceService


def test_batch_history_limits_provider_symbols_and_reports_deferred_work():
    store = MagicMock()
    store.get_quotes.return_value = []
    market = MagicMock()
    market.download_batch.return_value = {
        "AAA": pd.DataFrame(
            {
                "date": pd.date_range("2026-01-01", periods=30),
                "open": [1.0] * 30,
                "high": [1.1] * 30,
                "low": [0.9] * 30,
                "close": [1.0] * 30,
                "volume": [1000] * 30,
            }
        )
    }
    market.last_batch_meta = {"source": "fmp"}
    service = PriceService(store=store, market=market)

    service.download_batch(
        ["AAA", "BBB", "CCC"],
        period="1mo",
        min_bars=20,
        provider_symbol_budget=1,
    )

    requested = market.download_batch.call_args.args[0]
    assert requested == ["AAA"]
    assert service.last_batch_meta["provider_requested"] == 1
    assert service.last_batch_meta["provider_deferred"] == 2
