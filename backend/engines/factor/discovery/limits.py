"""Resource and complexity limits for Factor Discovery DSL parsing and compilation."""
from __future__ import annotations

from dataclasses import dataclass


FACTOR_DSL_V1 = "factor-dsl-v1"
COMPILER_VERSION = "factor-compiler-v1"


@dataclass(frozen=True)
class FactorDslLimits:
    max_source_length: int = 16_384
    max_tokens: int = 2_048
    max_ast_nodes: int = 256
    max_ast_depth: int = 32
    max_identifier_length: int = 128
    max_numeric_literal_length: int = 64
    max_rolling_window: int = 2_520
    max_lag_periods: int = 2_520


@dataclass(frozen=True)
class FactorCompileLimits:
    max_ast_nodes: int = 256
    max_ast_depth: int = 32
    max_distinct_fields: int = 64
    max_total_lookback: int = 5_040
    max_nested_rolling_depth: int = 16
