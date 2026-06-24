"""Raw penny liquidity / volume metrics separate from normalized scores."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

import pandas as pd

from data.price_service import avg_dollar_volume_from_history
from scoring.metrics import safe_float
from scoring.technical import atr_percent, spread_proxy_score

# Ignore baselines below this share count — avoids divide-by-near-zero ratios.
_MIN_BASELINE_VOLUME = 100.0
# Gap / ATR warning thresholds (percent).
_EXTREME_GAP_PCT = 8.0
_HIGH_ATR_PCT = 12.0
# Relative volume with weak same-day price move (score scale ~50 = flat).
_UNCONFIRMED_VOLUME_RATIO = 2.5
_FLAT_MOMENTUM_SCORE = 52.0


@dataclass
class PennyLiquidityMetrics:
    current_volume: float | None = None
    average_volume_20d: float | None = None
    relative_volume_ratio: float | None = None
    relative_volume_score: float = 0.0
    average_dollar_volume_20d: float | None = None
    atr_percent: float | None = None
    gap_percent: float | None = None
    spread_estimate_pct: float | None = None
    spread_score: float | None = None
    warnings: list[str] = field(default_factory=list)

    def to_metrics_dict(self) -> dict[str, float | list[str] | None]:
        """Flatten for scan candidate metrics (JSON-serializable)."""
        out: dict[str, float | list[str] | None] = {}
        for key, val in asdict(self).items():
            if key == "warnings":
                out["liquidity_warnings"] = list(val)
                continue
            if val is None:
                continue
            if isinstance(val, float):
                if key in ("relative_volume_ratio", "gap_percent", "spread_estimate_pct", "atr_percent"):
                    out[key] = round(val, 2)
                elif key == "relative_volume_score":
                    out[key] = round(val, 1)
                    out["volume_signal_score"] = round(val, 1)
                else:
                    out[key] = round(val, 2) if key != "current_volume" else round(val, 0)
            else:
                out[key] = val
        if self.relative_volume_ratio is not None:
            out["volume_ratio"] = round(self.relative_volume_ratio, 2)
        return out


def relative_volume_components(
    volume: pd.Series,
    *,
    lookback: int = 20,
) -> tuple[float | None, float | None, float | None]:
    """
    Return (baseline_avg, current_volume, ratio).

    Baseline uses prior completed bars only — current bar is excluded.
    """
    if volume is None or len(volume) < lookback + 1:
        return None, None, None

    baseline_series = volume.iloc[-lookback - 1 : -1].astype(float)
    current_raw = volume.iloc[-1]
    if pd.isna(current_raw):
        baseline = float(baseline_series.mean()) if len(baseline_series) else None
        return baseline, None, None

    current = float(current_raw)
    if baseline_series.empty:
        return None, current, None

    baseline = float(baseline_series.mean())
    if baseline <= 0 or baseline < _MIN_BASELINE_VOLUME:
        return baseline, current, None

    return baseline, current, current / baseline


def relative_volume_ratio_from_df(df: pd.DataFrame | None, lookback: int = 20) -> float | None:
    if df is None or df.empty or "volume" not in df.columns:
        return None
    _, _, ratio = relative_volume_components(df["volume"], lookback=lookback)
    return ratio


def relative_volume_score_from_ratio(ratio: float | None, *, cap: float = 3.0) -> float:
    """Map raw relative volume to 0–100 (3× baseline → 100)."""
    if ratio is None or ratio <= 0:
        return 0.0
    capped = min(float(ratio), cap)
    return max(0.0, min(100.0, capped / cap * 100.0))


def average_volume_20d_excluding_current(df: pd.DataFrame | None, lookback: int = 20) -> float | None:
    if df is None or df.empty or len(df) < lookback + 1:
        return None
    baseline, _, _ = relative_volume_components(df["volume"], lookback=lookback)
    return baseline


def average_dollar_volume_20d_excluding_current(df: pd.DataFrame | None, lookback: int = 20) -> float | None:
    if df is None or df.empty or len(df) < lookback + 1:
        return None
    tail = df.iloc[-lookback - 1 : -1]
    if tail.empty:
        return None
    return float((tail["close"].astype(float) * tail["volume"].astype(float)).mean())


def gap_percent_latest(df: pd.DataFrame | None) -> float | None:
    if df is None or len(df) < 2:
        return None
    prev_close = safe_float(df["close"].iloc[-2])
    open_px = safe_float(df["open"].iloc[-1])
    if prev_close <= 0:
        return None
    return (open_px / prev_close - 1.0) * 100.0


def spread_estimate_pct(df: pd.DataFrame | None) -> float | None:
    if df is None or df.empty:
        return None
    row = df.iloc[-1]
    close = safe_float(row.get("close"))
    if close <= 0:
        return None
    high = safe_float(row.get("high"))
    low = safe_float(row.get("low"))
    return (high - low) / close * 100.0


def compute_penny_liquidity_metrics(
    df: pd.DataFrame | None,
    *,
    lookback: int = 20,
) -> PennyLiquidityMetrics:
    warnings: list[str] = []
    if df is None or df.empty:
        return PennyLiquidityMetrics(warnings=["missing_history"])

    baseline, current, ratio = relative_volume_components(
        df["volume"],
        lookback=lookback,
    )
    score = relative_volume_score_from_ratio(ratio)

    if baseline is not None and baseline <= 0:
        warnings.append("zero_volume_baseline")
    elif baseline is not None and baseline < _MIN_BASELINE_VOLUME:
        warnings.append("extremely_low_volume_baseline")
    if current is None:
        warnings.append("missing_current_volume")

    adv = average_dollar_volume_20d_excluding_current(df, lookback=lookback)
    if adv is None:
        adv = avg_dollar_volume_from_history(df, lookback=lookback)

    atr_pct = atr_percent(df)
    gap_pct = gap_percent_latest(df)
    spread_pct = spread_estimate_pct(df)
    spread_score = spread_proxy_score(df)

    metrics = PennyLiquidityMetrics(
        current_volume=current,
        average_volume_20d=baseline,
        relative_volume_ratio=ratio,
        relative_volume_score=score,
        average_dollar_volume_20d=adv,
        atr_percent=atr_pct,
        gap_percent=gap_pct,
        spread_estimate_pct=spread_pct,
        spread_score=spread_score,
        warnings=warnings,
    )
    return metrics


def detect_penny_risk_warnings(
    metrics: PennyLiquidityMetrics,
    df: pd.DataFrame | None,
    *,
    momentum_5d_score: float | None = None,
    min_dollar_volume_warn: float = 1_000_000.0,
    data_quality_score: float | None = None,
    reconcile_flags: list[str] | None = None,
) -> list[str]:
    """High-risk conditions surfaced as warnings (not hard rejects)."""
    out: list[str] = []

    ratio = metrics.relative_volume_ratio
    if ratio is not None and ratio >= _UNCONFIRMED_VOLUME_RATIO:
        mom = momentum_5d_score
        if mom is None and df is not None and len(df) >= 6:
            from scoring.technical import momentum_score

            mom = momentum_score(df, 5)
        if mom is not None and mom <= _FLAT_MOMENTUM_SCORE:
            out.append("abnormal_volume_without_price_confirmation")

    if metrics.gap_percent is not None and abs(metrics.gap_percent) >= _EXTREME_GAP_PCT:
        out.append("extreme_gap")

    if metrics.atr_percent is not None and metrics.atr_percent >= _HIGH_ATR_PCT:
        out.append("very_high_atr")

    if metrics.average_dollar_volume_20d is not None and metrics.average_dollar_volume_20d < min_dollar_volume_warn:
        out.append("insufficient_liquidity")

    if metrics.spread_estimate_pct is not None and metrics.spread_estimate_pct >= 10.0:
        out.append("wide_intraday_spread")

    if data_quality_score is not None and data_quality_score < 45:
        out.append("potential_stale_quote")

    for flag in reconcile_flags or []:
        lower = flag.lower()
        if "split" in lower or "corporate" in lower or "dilut" in lower:
            out.append("possible_corporate_action_distortion")
            break

    return out
