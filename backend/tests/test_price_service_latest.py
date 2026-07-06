"""Latest price helpers — live quote during market hours."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd

from data.price_service import PriceService


def test_get_latest_price_prefers_live_quote_during_regular_hours():
    ps = PriceService(store=MagicMock(), market=MagicMock())
    ps.market.get_quote.return_value = {"currentPrice": 2.07, "open": 2.22, "high": 2.22, "low": 2.05}
    with patch("services.data_freshness_service.get_market_session_band", return_value="regular"):
        price = ps.get_latest_price("ALXO")
    assert price == 2.07
    ps.get_history = MagicMock()
    ps.get_history.assert_not_called()


def test_get_latest_price_falls_back_to_history_when_quote_missing():
    ps = PriceService(store=MagicMock(), market=MagicMock())
    ps.market.get_quote.return_value = {}
    hist = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-06-29"]),
            "open": [2.0],
            "high": [2.25],
            "low": [1.95],
            "close": [2.2],
            "volume": [1000.0],
        }
    )
    ps.get_history = MagicMock(return_value=hist)
    with patch("services.data_freshness_service.get_market_session_band", return_value="regular"):
        price = ps.get_latest_price("ALXO")
    assert price == 2.2


def test_refresh_latest_price_persists_live_bar_and_refreshes_history():
    ps = PriceService(store=MagicMock(), market=MagicMock())
    ps.market.get_quote.return_value = {
        "currentPrice": 2.07,
        "open": 2.22,
        "high": 2.22,
        "low": 2.05,
    }
    ps.store.get_quotes.return_value = []
    ps.get_history = MagicMock(return_value=pd.DataFrame())
    ps._persist = MagicMock()

    with patch.object(ps, "_session_date_et", return_value=__import__("datetime").date(2026, 7, 1)):
        price = ps.refresh_latest_price("ALXO", force=True)

    assert price == 2.07
    ps._persist.assert_called_once()
    ps.get_history.assert_called_with("ALXO", period="5d", force_refresh=True)
