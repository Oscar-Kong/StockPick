"""Typed policy configuration for the daily trading plan engine."""
from __future__ import annotations

from datetime import time

from pydantic import BaseModel, Field


class DailyTradingPolicy(BaseModel):
  """Hard and soft trading-discipline controls — single source of truth."""

  max_short_term_exposure: float = Field(default=0.50, ge=0.0, le=1.0)
  max_active_short_term_positions: int = Field(default=1, ge=0)
  minimum_focus_symbols: int = Field(default=3, ge=1)
  maximum_focus_symbols: int = Field(default=5, ge=1)
  entry_not_before_et: time = Field(default_factory=lambda: time(10, 0))
  stop_loss_pct: float = Field(default=0.05, ge=0.0, le=1.0)
  partial_profit_pct: float = Field(default=0.10, ge=0.0, le=1.0)
  partial_profit_fraction: float = Field(default=0.50, ge=0.0, le=1.0)
  leverage_allowed: bool = False
  short_term_bucket: str = "penny"
  trend_confirmed_min_score: float = 60.0
  liquidity_min_score: float = 45.0
  data_confidence_min: float = 70.0
  min_risk_reward_ratio: float = 1.5
  volume_relative_breakout_min: float = 1.5
  volume_relative_distribution_min: float = 2.0


DEFAULT_DAILY_TRADING_POLICY = DailyTradingPolicy()
