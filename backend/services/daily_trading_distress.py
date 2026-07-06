"""Distressed-security rejection for daily trading plan candidates."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from data.quality_filters import (
  QualityFilterResult,
  apply_quality_filters,
  is_likely_delisted,
  is_otc_symbol,
)
from models.schemas import Bucket
from scoring.data_quality import should_exclude_low_quality

DISTRESS_BANKRUPTCY_KEYWORDS = (
  "bankruptcy",
  "chapter 11",
  "chapter 7",
  "going concern",
  "delisting",
  "deficiency notice",
  "non-compliance",
  "late filing",
  "sec investigation",
  "trading halt",
  "halted",
)


@dataclass
class DistressCheckResult:
  rejected: bool
  reasons: list[str] = field(default_factory=list)
  insufficient_data: list[str] = field(default_factory=list)
  checks_run: list[str] = field(default_factory=list)


def evaluate_distress(
  *,
  symbol: str,
  price: float | None,
  history: Any,
  info: dict | None,
  metrics: dict | None,
  quality_score: float | None,
  hist_len: int,
  bucket: Bucket = Bucket.penny,
  scan_validated: bool = False,
) -> DistressCheckResult:
  """Reject distressed names when evidence exists; never reject on missing optional data alone."""
  result = DistressCheckResult(rejected=False)
  sym = symbol.upper().strip()

  result.checks_run.append("otc")
  if is_otc_symbol(sym, info):
    result.rejected = True
    result.reasons.append("OTC/pink-sheet security excluded")
    return result

  result.checks_run.append("delisting")
  if history is not None and is_likely_delisted(sym, history, info):
    result.rejected = True
    result.reasons.append("Delisted or stale price history")
    return result

  if price is None or price <= 0:
    result.insufficient_data.append("price_unavailable")
  elif not scan_validated:
    result.checks_run.append("quality_filters")
    qf: QualityFilterResult = apply_quality_filters(sym, bucket, float(price), history, info)
    if not qf.passed:
      result.rejected = True
      result.reasons.extend(qf.reasons)
      return result
  else:
    result.checks_run.append("quality_filters_scan_validated")
    if is_otc_symbol(sym, info):
      result.rejected = True
      result.reasons.append("OTC/pink-sheet security excluded")
      return result

  result.checks_run.append("data_quality")
  exclude, exclude_reason = should_exclude_low_quality(quality_score, hist_len)
  if exclude and not (scan_validated and quality_score is not None and quality_score >= 60):
    result.rejected = True
    result.reasons.append(exclude_reason or "Low data quality score")
    return result

  metrics = metrics or {}
  result.checks_run.append("liquidity_warnings")
  liq_warnings = metrics.get("liquidity_warnings") or []
  if isinstance(liq_warnings, list):
    for w in liq_warnings:
      wl = str(w).lower()
      if "extremely" in wl or "illiquid" in wl:
        result.rejected = True
        result.reasons.append(str(w))

  result.checks_run.append("halt_flag")
  halt = metrics.get("trading_halt") or (info or {}).get("tradingHalted")
  if halt is True:
    result.rejected = True
    result.reasons.append("Active trading halt")

  result.checks_run.append("news_distress")
  red_flags = metrics.get("news_red_flags") or metrics.get("red_flags") or []
  headlines = " ".join(str(h) for h in (metrics.get("news_headlines") or [])).lower()
  text_blob = headlines + " " + " ".join(str(r) for r in red_flags).lower()
  for kw in DISTRESS_BANKRUPTCY_KEYWORDS:
    if kw in text_blob:
      result.rejected = True
      result.reasons.append(f"Distress signal in news/context: {kw}")
      break

  adv = metrics.get("average_dollar_volume_20d")
  if adv is not None:
    result.checks_run.append("dollar_volume")
    if float(adv) < 50_000:
      result.rejected = True
      result.reasons.append("Extremely poor liquidity (ADV < $50k)")
  elif quality_score is None:
    result.insufficient_data.append("liquidity_metrics")

  dq_flags = metrics.get("data_quality_flags") or []
  if isinstance(dq_flags, list):
    critical = [f for f in dq_flags if "critical" in str(f).lower()]
    if critical:
      result.rejected = True
      result.reasons.append("Unresolved critical data-quality warnings")

  return result
