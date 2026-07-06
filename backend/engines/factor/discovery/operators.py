"""Time-series and element-wise operator execution."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from engines.factor.discovery.panel_models import FactorExecutionConfig, OperatorDiagnosticsCollector
from models.schemas_factor_discovery import LogDomainPolicy, ZeroDivisionPolicy


@dataclass
class ExecutionContext:
    index: pd.Index
    config: FactorExecutionConfig
    diagnostics: OperatorDiagnosticsCollector = field(default_factory=OperatorDiagnosticsCollector)


def _per_symbol(series: pd.Series, fn) -> pd.Series:
    return series.groupby(level="symbol", group_keys=False).apply(fn)


def _group_shift(series: pd.Series, periods: int) -> pd.Series:
    return series.groupby(level="symbol", group_keys=False).shift(periods)


def _group_pct_change(series: pd.Series, periods: int, ctx: ExecutionContext) -> pd.Series:
    def _pct(s: pd.Series) -> pd.Series:
        prior = s.shift(periods)
        out = (s - prior) / prior
        if ctx.config.pct_change_zero_prior == "nan":
            out = out.where(prior != 0)
        return out.replace([np.inf, -np.inf], np.nan)

    shifted = series.groupby(level="symbol", group_keys=False).apply(_pct)
    return shifted.reindex(series.index)


def _rolling_min_periods(window: int, config: FactorExecutionConfig) -> int:
    if config.rolling_min_periods_policy == "full_window":
        return window
    return 1


def apply_abs(series: pd.Series, _ctx: ExecutionContext) -> pd.Series:
    return series.abs()


def apply_negate(series: pd.Series, _ctx: ExecutionContext) -> pd.Series:
    return -series


def apply_sign(series: pd.Series, _ctx: ExecutionContext) -> pd.Series:
    return np.sign(series)


def apply_log(series: pd.Series, ctx: ExecutionContext, policy: LogDomainPolicy) -> pd.Series:
    invalid = series <= 0
    ctx.diagnostics.invalid_log_domain_count += int(invalid.sum())
    if policy == LogDomainPolicy.NULL_ON_NON_POSITIVE:
        return series.where(series > 0).apply(np.log)
    if policy == LogDomainPolicy.ABS_LOG:
        return np.log(series.abs().where(series != 0))
    raise ValueError(f"unsupported log policy: {policy}")


def apply_add(left: pd.Series, right: pd.Series, _ctx: ExecutionContext) -> pd.Series:
    return left + right


def apply_subtract(left: pd.Series, right: pd.Series, _ctx: ExecutionContext) -> pd.Series:
    return left - right


def apply_multiply(left: pd.Series, right: pd.Series, _ctx: ExecutionContext) -> pd.Series:
    return left * right


def apply_divide(left: pd.Series, right: pd.Series, ctx: ExecutionContext, policy: ZeroDivisionPolicy) -> pd.Series:
    zero_den = right == 0
    ctx.diagnostics.zero_denominator_count += int(zero_den.sum())
    if policy == ZeroDivisionPolicy.NULL:
        return left / right.replace(0, np.nan)
    if policy == ZeroDivisionPolicy.ZERO:
        return left / right.replace(0, np.nan).fillna(np.inf).where(~zero_den, 0.0)
    if policy == ZeroDivisionPolicy.EPSILON:
        eps = 1e-12
        return left / right.where(~zero_den, eps)
    raise ValueError(f"unsupported zero policy: {policy}")


def apply_min(left: pd.Series, right: pd.Series, _ctx: ExecutionContext) -> pd.Series:
    return pd.concat([left, right], axis=1).min(axis=1)


def apply_max(left: pd.Series, right: pd.Series, _ctx: ExecutionContext) -> pd.Series:
    return pd.concat([left, right], axis=1).max(axis=1)


def apply_lag(series: pd.Series, periods: int, ctx: ExecutionContext) -> pd.Series:
    out = _group_shift(series, periods)
    ctx.diagnostics.warm_up_rows += int(out.isna().sum() - series.isna().sum())
    return out


def apply_delta(series: pd.Series, periods: int, ctx: ExecutionContext) -> pd.Series:
    out = series.groupby(level="symbol", group_keys=False).diff(periods)
    ctx.diagnostics.warm_up_rows += int(out.isna().sum() - series.isna().sum())
    return out


def apply_pct_change(series: pd.Series, periods: int, ctx: ExecutionContext) -> pd.Series:
    out = _group_pct_change(series, periods, ctx)
    ctx.diagnostics.warm_up_rows += int(out.isna().sum() - series.isna().sum())
    return out


def apply_rolling_mean(series: pd.Series, window: int, ctx: ExecutionContext) -> pd.Series:
    mp = _rolling_min_periods(window, ctx.config)

    def _roll(s: pd.Series) -> pd.Series:
        return s.rolling(window, min_periods=mp).mean()

    return series.groupby(level="symbol", group_keys=False).apply(_roll).reindex(series.index)


def apply_rolling_std(series: pd.Series, window: int, ctx: ExecutionContext) -> pd.Series:
    mp = _rolling_min_periods(window, ctx.config)
    ddof = ctx.config.rolling_std_ddof

    def _roll(s: pd.Series) -> pd.Series:
        return s.rolling(window, min_periods=mp).std(ddof=ddof)

    return series.groupby(level="symbol", group_keys=False).apply(_roll).reindex(series.index)


def apply_rolling_min(series: pd.Series, window: int, ctx: ExecutionContext) -> pd.Series:
    mp = _rolling_min_periods(window, ctx.config)

    def _roll(s: pd.Series) -> pd.Series:
        return s.rolling(window, min_periods=mp).min()

    return series.groupby(level="symbol", group_keys=False).apply(_roll).reindex(series.index)


def apply_rolling_max(series: pd.Series, window: int, ctx: ExecutionContext) -> pd.Series:
    mp = _rolling_min_periods(window, ctx.config)

    def _roll(s: pd.Series) -> pd.Series:
        return s.rolling(window, min_periods=mp).max()

    return series.groupby(level="symbol", group_keys=False).apply(_roll).reindex(series.index)


def apply_rolling_sum(series: pd.Series, window: int, ctx: ExecutionContext) -> pd.Series:
    mp = _rolling_min_periods(window, ctx.config)

    def _roll(s: pd.Series) -> pd.Series:
        return s.rolling(window, min_periods=mp).sum()

    return series.groupby(level="symbol", group_keys=False).apply(_roll).reindex(series.index)


def apply_rolling_correlation(left: pd.Series, right: pd.Series, window: int, ctx: ExecutionContext) -> pd.Series:
    mp = _rolling_min_periods(window, ctx.config)
    combined = pd.DataFrame({"l": left, "r": right})

    def _corr(g: pd.DataFrame) -> pd.Series:
        return g["l"].rolling(window, min_periods=mp).corr(g["r"])

    return combined.groupby(level="symbol", group_keys=False).apply(_corr).reindex(left.index)


def sanitize_series(series: pd.Series, ctx: ExecutionContext) -> pd.Series:
    arr = series.to_numpy(dtype=float, copy=True)
    inf_mask = np.isinf(arr)
    if inf_mask.any():
        ctx.diagnostics.invalid_log_domain_count += int(inf_mask.sum())
        arr[inf_mask] = np.nan
    return pd.Series(arr, index=series.index, name=series.name)
