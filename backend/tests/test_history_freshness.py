"""Tests for OHLC history freshness assessment and PriceService refresh behavior."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from data.history_freshness import (
    assess_history_freshness,
    expected_last_completed_session,
    merge_history_frames,
    session_lag_business_days,
)
from data.price_service import PriceService


def _make_df(dates: list[str], close: float = 10.0) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.to_datetime(dates),
            "open": close,
            "high": close + 1,
            "low": close - 1,
            "close": close,
            "volume": 1_000_000,
        }
    )


def test_fresh_local_history_when_last_bar_is_current():
    expected = expected_last_completed_session()
    dates = [(expected - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(250, -1, -1)]
    df = _make_df(dates)
    info = assess_history_freshness(df, min_bars=200)
    assert info.is_sufficient
    assert info.is_fresh
    assert info.needs_refresh is False
    assert info.last_date == expected


def test_stale_local_history_triggers_refresh_need():
    old_end = date(2026, 6, 8)
    dates = [(old_end - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(250, -1, -1)]
    df = _make_df(dates)
    info = assess_history_freshness(df, min_bars=200, now=datetime(2026, 6, 15, 12, tzinfo=timezone.utc))
    assert info.is_sufficient
    assert info.is_fresh is False
    assert info.needs_refresh is True
    assert info.last_date == old_end


def test_merge_deduplicates_prefers_provider_rows():
    local = _make_df(["2026-06-01", "2026-06-02"], close=10.0)
    provider = _make_df(["2026-06-02", "2026-06-03"], close=20.0)
    merged = merge_history_frames(local, provider)
    assert len(merged) == 3
    june2 = merged[merged["date"] == pd.Timestamp("2026-06-02")].iloc[0]
    assert float(june2["close"]) == 20.0


def test_weekend_expected_session_is_prior_weekday():
    # Saturday June 13 2026
    now = datetime(2026, 6, 13, 12, 0, tzinfo=timezone.utc)
    expected = expected_last_completed_session(now)
    assert expected.weekday() < 5
    assert expected <= date(2026, 6, 12)


@patch("data.price_service.PriceService._persist")
def test_price_service_fetches_when_local_stale(mock_persist):
    old_end = date(2026, 6, 8)
    dates = [(old_end - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(250, -1, -1)]
    local_df = _make_df(dates)

    fresh_end = date(2026, 6, 12)
    fresh_dates = [(fresh_end - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(30, -1, -1)]
    provider_df = _make_df(fresh_dates, close=15.0)

    store = MagicMock()
    store.get_quotes.return_value = local_df.to_dict("records")
    market = MagicMock()
    market.get_history.return_value = provider_df

    ps = PriceService(store=store, market=market)
    with patch("data.price_service.assess_history_freshness") as mock_assess:
        mock_assess.side_effect = [
            assess_history_freshness(local_df, 200, now=datetime(2026, 6, 15, tzinfo=timezone.utc)),
            assess_history_freshness(
                merge_history_frames(local_df, provider_df), 200, now=datetime(2026, 6, 15, tzinfo=timezone.utc)
            ),
        ]
        df, meta = ps.get_history_with_meta("TEST", period="1y", force_refresh=False)
    market.get_history.assert_called_once()
    assert meta["price_history_is_stale"] is False
    assert not df.empty


@patch("data.price_service.PriceService._persist")
def test_force_refresh_bypasses_fresh_local(mock_persist):
    expected = expected_last_completed_session()
    dates = [(expected - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(250, -1, -1)]
    local_df = _make_df(dates)
    provider_df = _make_df(dates[-5:], close=99.0)

    store = MagicMock()
    store.get_quotes.return_value = local_df.to_dict("records")
    market = MagicMock()
    market.get_history.return_value = provider_df

    ps = PriceService(store=store, market=market)
    ps.get_history_with_meta("TEST", period="1y", force_refresh=True)
    market.get_history.assert_called_once()
    assert market.get_history.call_args.kwargs.get("skip_cache") is True


def test_provider_failure_returns_stale_local_with_metadata():
    old_end = date(2026, 6, 8)
    dates = [(old_end - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(250, -1, -1)]
    local_df = _make_df(dates)

    store = MagicMock()
    store.get_quotes.return_value = [
        {
            "date": d,
            "open": 10.0,
            "high": 11.0,
            "low": 9.0,
            "close": 10.0,
            "volume": 1000.0,
        }
        for d in dates
    ]
    market = MagicMock()
    market.get_history.return_value = pd.DataFrame()

    ps = PriceService(store=store, market=market)
    df, meta = ps.get_history_with_meta("TEST", period="1y", force_refresh=False)
    assert not df.empty
    assert meta["price_history_is_stale"] is True
    assert meta["price_history_last_date"] == "2026-06-08"


def test_session_lag_counts_weekdays():
    lag = session_lag_business_days(date(2026, 6, 8), date(2026, 6, 12))
    assert lag >= 3
