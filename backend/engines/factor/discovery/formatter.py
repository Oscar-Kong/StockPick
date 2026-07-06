"""Canonical AST-to-DSL formatter for factor-dsl-v1."""
from __future__ import annotations

from models.schemas_factor_discovery import (
    AstNode,
    BinaryNode,
    BinaryOperator,
    ConditionalNode,
    ConstantNode,
    CrossSectionNode,
    CrossSectionOperator,
    FieldNode,
    LogDomainPolicy,
    NeutralizationKey,
    NeutralizeNode,
    RollingNode,
    RollingOperator,
    UnaryNode,
    UnaryOperator,
    ZeroDivisionPolicy,
)

_UNARY_NAME = {
    UnaryOperator.ABS: "abs",
    UnaryOperator.NEGATE: "negate",
    UnaryOperator.LOG: "log",
    UnaryOperator.SIGN: "sign",
}

_BINARY_NAME = {
    BinaryOperator.ADD: "add",
    BinaryOperator.SUBTRACT: "subtract",
    BinaryOperator.MULTIPLY: "multiply",
    BinaryOperator.DIVIDE: "divide",
    BinaryOperator.MIN: "min",
    BinaryOperator.MAX: "max",
}

_ROLLING_NAME = {
    RollingOperator.LAG: "lag",
    RollingOperator.DELTA: "delta",
    RollingOperator.PCT_CHANGE: "pct_change",
    RollingOperator.ROLLING_MEAN: "rolling_mean",
    RollingOperator.ROLLING_STD: "rolling_std",
    RollingOperator.ROLLING_MIN: "rolling_min",
    RollingOperator.ROLLING_MAX: "rolling_max",
    RollingOperator.ROLLING_SUM: "rolling_sum",
    RollingOperator.ROLLING_CORRELATION: "rolling_correlation",
}

_CROSS_NAME = {
    CrossSectionOperator.RANK: "rank",
    CrossSectionOperator.PERCENTILE_RANK: "percentile_rank",
    CrossSectionOperator.ZSCORE: "zscore",
    CrossSectionOperator.WINSORIZE: "winsorize",
}

_NEUTRALIZE_NAME = {
    NeutralizationKey.SECTOR: "sector_neutralize",
    NeutralizationKey.INDUSTRY: "industry_neutralize",
    NeutralizationKey.MARKET_CAP: "market_cap_neutralize",
}

_LOG_POLICY_DSL = {
    LogDomainPolicy.NULL_ON_NON_POSITIVE: "null",
    LogDomainPolicy.ABS_LOG: "abs_log",
}

_ZERO_POLICY_DSL = {
    ZeroDivisionPolicy.NULL: "null",
    ZeroDivisionPolicy.ZERO: "zero",
    ZeroDivisionPolicy.EPSILON: "epsilon",
}


def _format_number(value: float) -> str:
    if value == int(value):
        return str(int(value))
    text = format(value, ".15g")
    if "e" in text or "E" in text:
        raise ValueError("non-canonical numeric representation")
    return text


def _format_args(parts: list[str]) -> str:
    return ",".join(parts)


def format_factor_expression(node: AstNode) -> str:
    """Render AST as canonical factor-dsl-v1 source."""
    if isinstance(node, FieldNode):
        return node.field_id
    if isinstance(node, ConstantNode):
        return _format_number(node.value)
    if isinstance(node, UnaryNode):
        name = _UNARY_NAME[node.op]
        inner = format_factor_expression(node.child)
        if node.op == UnaryOperator.LOG:
            policy = _LOG_POLICY_DSL[node.log_policy]
            if policy != "null":
                return f'{name}({inner},invalid_policy="{policy}")'
            return f'{name}({inner},invalid_policy="null")'
        return f"{name}({inner})"
    if isinstance(node, BinaryNode):
        name = _BINARY_NAME[node.op]
        left = format_factor_expression(node.left)
        right = format_factor_expression(node.right)
        if node.op == BinaryOperator.DIVIDE:
            policy = _ZERO_POLICY_DSL[node.zero_policy]
            return f'{name}({left},{right},zero_policy="{policy}")'
        return f"{name}({left},{right})"
    if isinstance(node, RollingNode):
        name = _ROLLING_NAME[node.op]
        left = format_factor_expression(node.child)
        window = str(node.window)
        if node.op == RollingOperator.ROLLING_CORRELATION:
            assert node.right is not None
            right = format_factor_expression(node.right)
            return f"{name}({left},{right},{window})"
        return f"{name}({left},{window})"
    if isinstance(node, CrossSectionNode):
        name = _CROSS_NAME[node.op]
        inner = format_factor_expression(node.child)
        if node.op == CrossSectionOperator.WINSORIZE:
            lower = _format_number(node.winsorize_lower)
            upper = _format_number(node.winsorize_upper)
            return f"{name}({inner},lower={lower},upper={upper})"
        return f"{name}({inner})"
    if isinstance(node, NeutralizeNode):
        name = _NEUTRALIZE_NAME[node.key]
        inner = format_factor_expression(node.child)
        return f"{name}({inner})"
    if isinstance(node, ConditionalNode):
        raise ValueError("CONDITIONAL nodes cannot be formatted in factor-dsl-v1")
    raise TypeError(f"unknown AST node: {type(node)}")
