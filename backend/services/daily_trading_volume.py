"""Measurable volume-behavior classification for daily trading plan."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from services.daily_trading_policy import DailyTradingPolicy


@dataclass
class VolumeClassification:
  classification: str
  measurements: dict[str, Any] = field(default_factory=dict)
  thresholds: dict[str, Any] = field(default_factory=dict)
  rationale: str = ""


def classify_volume_behavior(
  df: pd.DataFrame | None,
  *,
  policy: DailyTradingPolicy | None = None,
  support_level: float | None = None,
  resistance_level: float | None = None,
) -> VolumeClassification:
  """Classify volume using price/volume measurements — no speculative labels."""
  pol = policy or DailyTradingPolicy()
  thresholds = {
    "relative_volume_breakout_min": pol.volume_relative_breakout_min,
    "relative_volume_distribution_min": pol.volume_relative_distribution_min,
    "support_buffer_pct": 0.02,
    "contraction_volume_decline_min": 0.15,
    "capitulation_return_pct": -0.12,
  }

  if df is None or df.empty or len(df) < 25:
    return VolumeClassification(
      classification="inconclusive",
      thresholds=thresholds,
      rationale="Insufficient price/volume history",
    )

  close = df["close"].astype(float)
  volume = df["volume"].astype(float)
  price = float(close.iloc[-1])
  ret_5d = (price - float(close.iloc[-6])) / float(close.iloc[-6]) if len(close) >= 6 else 0.0

  baseline = float(volume.iloc[-21:-1].mean()) if len(volume) >= 21 else float(volume.iloc[:-1].mean())
  current_vol = float(volume.iloc[-1])
  rel_vol = current_vol / baseline if baseline > 0 else None

  window = df.iloc[-21:-1]
  support = support_level if support_level is not None else float(window["low"].min())
  resistance = resistance_level if resistance_level is not None else float(window["high"].max())
  above_support = price >= support * (1 - thresholds["support_buffer_pct"])

  vol_trend = None
  if len(volume) >= 6:
    recent = float(volume.iloc[-3:].mean())
    prior = float(volume.iloc[-6:-3].mean())
    if prior > 0:
      vol_trend = (recent - prior) / prior

  measurements = {
    "price": round(price, 4),
    "relative_volume": round(rel_vol, 3) if rel_vol is not None else None,
    "return_5d_pct": round(ret_5d * 100, 2),
    "support_level": round(support, 4),
    "resistance_level": round(resistance, 4),
    "above_support": above_support,
    "volume_trend_3v3_pct": round(vol_trend * 100, 2) if vol_trend is not None else None,
  }

  # Breakout confirmation
  if (
    rel_vol is not None
    and rel_vol >= thresholds["relative_volume_breakout_min"]
    and price >= resistance
    and float(df["close"].iloc[-1]) >= float(df["open"].iloc[-1])
  ):
    return VolumeClassification(
      classification="breakout_confirmation",
      measurements=measurements,
      thresholds=thresholds,
      rationale=(
        f"Close {price:.2f} at/above resistance {resistance:.2f} "
        f"with relative volume {rel_vol:.2f}x (≥ {thresholds['relative_volume_breakout_min']})"
      ),
    )

  # Possible distribution
  weak_close = float(df["close"].iloc[-1]) <= float(df["high"].iloc[-1]) * 0.985
  support_fail = price < support
  if rel_vol is not None and rel_vol >= thresholds["relative_volume_distribution_min"]:
    if weak_close or support_fail or ret_5d < -0.03:
      return VolumeClassification(
        classification="possible_distribution",
        measurements=measurements,
        thresholds=thresholds,
        rationale=(
          f"Elevated relative volume {rel_vol:.2f}x with "
          f"{'support failure' if support_fail else 'weak close or down-volume pressure'}"
        ),
      )

  # Constructive contraction
  if (
    vol_trend is not None
    and vol_trend <= -thresholds["contraction_volume_decline_min"]
    and above_support
    and ret_5d <= 0.02
  ):
    return VolumeClassification(
      classification="constructive_contraction",
      measurements=measurements,
      thresholds=thresholds,
      rationale=(
        f"Pullback/consolidation with volume declining {abs(vol_trend)*100:.1f}% "
        f"while price {price:.2f} holds above support {support:.2f}"
      ),
    )

  # Capitulation candidate
  if ret_5d <= thresholds["capitulation_return_pct"] and rel_vol is not None and rel_vol >= 2.0:
    stabilization = float(close.iloc[-1]) >= float(close.iloc[-2])
    if stabilization:
      return VolumeClassification(
        classification="capitulation_candidate",
        measurements=measurements,
        thresholds=thresholds,
        rationale=(
          f"5d return {ret_5d*100:.1f}% with {rel_vol:.2f}x volume and stabilization on latest bar"
        ),
      )

  # Contraction without support — inconclusive per spec
  if vol_trend is not None and vol_trend < 0 and not above_support:
    return VolumeClassification(
      classification="inconclusive",
      measurements=measurements,
      thresholds=thresholds,
      rationale="Volume contraction without confirmed support hold",
    )

  return VolumeClassification(
    classification="inconclusive",
    measurements=measurements,
    thresholds=thresholds,
    rationale="Volume does not provide a sufficiently reliable signal",
  )
