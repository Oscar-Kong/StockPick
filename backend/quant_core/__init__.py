"""Core financial time-series utilities (returns, labels, diagnostics)."""
from quant_core.diagnostics import (
    adf_test,
    autocorrelation_summary,
    excess_kurtosis,
    jarque_bera_test,
    skewness,
)
from quant_core.features import lag, rolling_mean, rolling_std, rolling_zscore
from quant_core.labels import (
    forward_excess_return_label,
    forward_return_label,
    large_move_label,
)
from quant_core.returns import (
    annualized_return,
    annualized_volatility,
    cumulative_simple_return,
    excess_returns,
    log_returns,
    max_drawdown,
    rolling_return,
    simple_returns,
)
from quant_core.validation import assert_aligned, validate_forward_labels

__all__ = [
    "adf_test",
    "annualized_return",
    "annualized_volatility",
    "assert_aligned",
    "autocorrelation_summary",
    "cumulative_simple_return",
    "excess_kurtosis",
    "excess_returns",
    "forward_excess_return_label",
    "forward_return_label",
    "jarque_bera_test",
    "lag",
    "large_move_label",
    "log_returns",
    "max_drawdown",
    "rolling_mean",
    "rolling_return",
    "rolling_std",
    "rolling_zscore",
    "simple_returns",
    "skewness",
    "validate_forward_labels",
]
