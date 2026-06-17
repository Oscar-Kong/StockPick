"""Tests for portfolio weight normalization and cash buffer."""
from __future__ import annotations

import pytest

from services.portfolio_optimizer import (
    WEIGHT_SUM_TOLERANCE,
    _normalize_weights,
    optimize_portfolio,
    validate_weight_constraints,
)


class TestValidateWeightConstraints:
    def test_feasible_constraints_pass(self):
        validate_weight_constraints(4, 0.25, 0.05)

    def test_infeasible_raises_clear_message(self):
        with pytest.raises(ValueError, match="maximum position weight"):
            validate_weight_constraints(4, 0.20, 0.05)


class TestNormalizeWeights:
    def test_cash_buffer_applied_once(self):
        raw = {"A": 1.0, "B": 1.0, "C": 1.0, "D": 1.0}
        weights = _normalize_weights(raw, max_weight=0.30, cash_buffer=0.05)
        total = sum(weights.values())
        assert abs(total - 0.95) <= WEIGHT_SUM_TOLERANCE

    def test_max_weight_clipping(self):
        raw = {"A": 10.0, "B": 1.0, "C": 1.0, "D": 1.0}
        weights = _normalize_weights(raw, max_weight=0.25, cash_buffer=0.0)
        assert all(w <= 0.25 + WEIGHT_SUM_TOLERANCE for w in weights.values())
        assert abs(sum(weights.values()) - 1.0) <= WEIGHT_SUM_TOLERANCE

    def test_infeasible_after_clip_raises(self):
        raw = {"A": 1.0, "B": 1.0, "C": 1.0, "D": 1.0}
        with pytest.raises(ValueError, match="maximum position weight"):
            _normalize_weights(raw, max_weight=0.20, cash_buffer=0.05)

    def test_empty_raw_raises(self):
        with pytest.raises(ValueError, match="No weights"):
            _normalize_weights({}, max_weight=0.30, cash_buffer=0.05)


class TestOptimizePortfolioValidation:
    def test_single_symbol_rejected(self):
        with pytest.raises(ValueError, match="at least 2"):
            optimize_portfolio(["AAPL"])

    def test_duplicate_symbols_deduped(self, monkeypatch):
        import services.portfolio_optimizer as po

        def fake_fallback(symbols, **kwargs):
            from services.portfolio_optimizer import OptimizeResult

            return OptimizeResult(
                optimizer="fallback",
                symbols_used=["AAPL", "MSFT"],
                excluded=[],
                weights={"AAPL": 0.475, "MSFT": 0.475},
            )

        monkeypatch.setattr(po, "_fallback_optimize", fake_fallback)
        monkeypatch.setattr(po, "PYPFOPT_ENABLED", False)
        result = optimize_portfolio(["AAPL", "aapl", "MSFT"], cash_buffer=0.05)
        assert len(result.symbols_used) == 2

    def test_empty_symbols_rejected(self):
        with pytest.raises(ValueError, match="at least 2"):
            optimize_portfolio(["", "  "])

    def test_missing_history_raises(self, monkeypatch):
        import services.portfolio_optimizer as po

        def empty_panel(symbols, period):
            import pandas as pd

            return pd.DataFrame(), symbols

        monkeypatch.setattr(po, "_price_panel", empty_panel)
        monkeypatch.setattr(po, "PYPFOPT_ENABLED", False)
        with pytest.raises(ValueError, match="at least 2 symbols"):
            optimize_portfolio(["AAPL", "MSFT"])
