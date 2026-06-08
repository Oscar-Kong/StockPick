"""Phase 5 unit tests — cost model and metrics."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engines.backtest.cost_model import trade_cost_usd
from engines.backtest.liquidity import avg_dollar_volume, cap_rebalance_notional
from engines.backtest.metrics import calmar_ratio, sortino_ratio


def test_trade_cost_bps():
    cost = trade_cost_usd(10_000, fee_bps=5, slip_bps=10)
    assert cost == 15.0


def test_adv_cap():
    hist = pd.DataFrame(
        {
            "volume": [1_000_000] * 20,
            "close": [10.0] * 20,
            "high": [10.0] * 20,
            "low": [10.0] * 20,
        }
    )
    adv = avg_dollar_volume(hist)
    assert adv == 10_000_000.0
    capped, note = cap_rebalance_notional("TEST", 5_000_000, 10.0, hist, participation_rate=0.1)
    assert capped == 1_000_000.0
    assert note is not None


def test_sortino_calmar():
    rets = pd.Series([0.01, -0.02, 0.015, -0.01, 0.02])
    assert sortino_ratio(rets) != 0
    assert calmar_ratio(12.0, -8.0) == 1.5


if __name__ == "__main__":
    test_trade_cost_bps()
    test_adv_cap()
    test_sortino_calmar()
    print("quant v2 phase5 tests passed")
