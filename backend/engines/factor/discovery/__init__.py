"""Factor Discovery DSL parser, formatter, and compiler."""
from __future__ import annotations

from .compiler import CompiledFactorPlan, compile_factor_definition, compile_factor_expression
from .errors import (
    FactorCompileError,
    FactorDslError,
    FactorDslLimitError,
    FactorDslParseError,
    FactorDslTokenizationError,
    ForbiddenFieldError,
    InvalidOperatorArgumentsError,
    UnknownFieldError,
    UnknownOperatorError,
    UnsupportedNodeError,
)
from .field_registry import (
    FactorDataSourcePolicy,
    FactorFieldRegistry,
    FactorFieldSpec,
    build_default_field_registry,
    default_data_source_policy,
)
from .formatter import format_factor_expression
from .executor import compute_factor_panel
from .limits import COMPILER_VERSION, FACTOR_DSL_V1, FactorCompileLimits, FactorDslLimits
from .panel_models import FactorExecutionConfig, FactorExecutionLimits, FactorExecutionResult, FactorInputPanel
from .parser import parse_factor_expression
from .result_hashing import EXECUTOR_VERSION
from .validation_engine import BenchmarkFactorPanel, validate_factor_execution
from .validation_models import FactorValidationArtifact, FactorValidationConfig, SealedTestAccess

__all__ = [
    "COMPILER_VERSION",
    "EXECUTOR_VERSION",
    "FACTOR_DSL_V1",
    "CompiledFactorPlan",
    "FactorExecutionConfig",
    "FactorExecutionLimits",
    "FactorExecutionResult",
    "FactorInputPanel",
    "FactorCompileError",
    "FactorCompileLimits",
    "FactorDataSourcePolicy",
    "FactorDslError",
    "FactorDslLimitError",
    "FactorDslLimits",
    "FactorDslParseError",
    "FactorDslTokenizationError",
    "FactorFieldRegistry",
    "FactorFieldSpec",
    "ForbiddenFieldError",
    "InvalidOperatorArgumentsError",
    "UnknownFieldError",
    "UnknownOperatorError",
    "UnsupportedNodeError",
    "build_default_field_registry",
    "compile_factor_definition",
    "compile_factor_expression",
    "compute_factor_panel",
    "default_data_source_policy",
    "format_factor_expression",
    "parse_factor_expression",
    "validate_factor_execution",
    "BenchmarkFactorPanel",
    "FactorValidationArtifact",
    "FactorValidationConfig",
    "SealedTestAccess",
]
