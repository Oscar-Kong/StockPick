"""Recursive-descent parser for factor-dsl-v1."""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any

from models.schemas_factor_discovery import (
    AstNode,
    BinaryNode,
    BinaryOperator,
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

from .errors import FactorDslLimitError, FactorDslParseError
from .limits import FACTOR_DSL_V1, FactorDslLimits
from .tokenizer import Token, TokenKind, tokenize

FIELD_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
_FORBIDDEN_FIELD_IDENTS = frozenset({"nan", "inf", "infinity"})

_UNARY_OPS = frozenset({"abs", "negate", "log", "sign"})
_BINARY_OPS = frozenset({"add", "subtract", "multiply", "divide", "min", "max"})
_LAG_OPS = frozenset({"lag", "delta", "pct_change"})
_ROLLING_OPS = frozenset(
    {"rolling_mean", "rolling_std", "rolling_min", "rolling_max", "rolling_sum", "rolling_correlation"}
)
_CROSS_OPS = frozenset({"rank", "percentile_rank", "zscore", "winsorize"})
_NEUTRALIZE_OPS = {
    "sector_neutralize": NeutralizationKey.SECTOR,
    "industry_neutralize": NeutralizationKey.INDUSTRY,
    "market_cap_neutralize": NeutralizationKey.MARKET_CAP,
}
_UNSUPPORTED_OPS = frozenset({"where"})

_DSL_TO_ROLLING = {
    "lag": RollingOperator.LAG,
    "delta": RollingOperator.DELTA,
    "pct_change": RollingOperator.PCT_CHANGE,
    "rolling_mean": RollingOperator.ROLLING_MEAN,
    "rolling_std": RollingOperator.ROLLING_STD,
    "rolling_min": RollingOperator.ROLLING_MIN,
    "rolling_max": RollingOperator.ROLLING_MAX,
    "rolling_sum": RollingOperator.ROLLING_SUM,
    "rolling_correlation": RollingOperator.ROLLING_CORRELATION,
}

_DSL_TO_BINARY = {
    "add": BinaryOperator.ADD,
    "subtract": BinaryOperator.SUBTRACT,
    "multiply": BinaryOperator.MULTIPLY,
    "divide": BinaryOperator.DIVIDE,
    "min": BinaryOperator.MIN,
    "max": BinaryOperator.MAX,
}

_DSL_TO_CROSS = {
    "rank": CrossSectionOperator.RANK,
    "percentile_rank": CrossSectionOperator.PERCENTILE_RANK,
    "zscore": CrossSectionOperator.ZSCORE,
    "winsorize": CrossSectionOperator.WINSORIZE,
}

_LOG_POLICY_MAP = {
    "null": LogDomainPolicy.NULL_ON_NON_POSITIVE,
    "null_on_non_positive": LogDomainPolicy.NULL_ON_NON_POSITIVE,
    "abs_log": LogDomainPolicy.ABS_LOG,
}

_ZERO_POLICY_MAP = {
    "null": ZeroDivisionPolicy.NULL,
    "zero": ZeroDivisionPolicy.ZERO,
    "epsilon": ZeroDivisionPolicy.EPSILON,
}


@dataclass
class _Arg:
    positional: AstNode | None = None
    keyword: str | None = None
    kw_value: str | float | None = None


class _Parser:
    def __init__(self, tokens: list[Token], *, limits: FactorDslLimits, dsl_version: str) -> None:
        self.tokens = tokens
        self.limits = limits
        self.dsl_version = dsl_version
        self.pos = 0
        self.node_count = 0
        self.max_depth_seen = 0

    def _current(self) -> Token:
        return self.tokens[self.pos]

    def _advance(self) -> Token:
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def _parse_error(self, code: str, message: str, tok: Token | None = None) -> FactorDslParseError:
        t = tok or self._current()
        return FactorDslParseError(
            code=code,
            message=message,
            offset=t.offset,
            line=t.line,
            column=t.column,
            token=t.value if t.kind != TokenKind.EOF else None,
        )

    def _expect(self, kind: TokenKind, *, code: str = "unexpected_token") -> Token:
        tok = self._current()
        if tok.kind != kind:
            raise self._parse_error(code, f"expected {kind.value}, got {tok.kind.value}")
        return self._advance()

    def _bump_node(self, depth: int) -> None:
        self.node_count += 1
        self.max_depth_seen = max(self.max_depth_seen, depth)
        if self.node_count > self.limits.max_ast_nodes:
            raise FactorDslLimitError(
                code="too_many_ast_nodes",
                message=f"AST node count exceeds maximum of {self.limits.max_ast_nodes}",
                offset=self._current().offset,
                line=self._current().line,
                column=self._current().column,
            )
        if depth > self.limits.max_ast_depth:
            raise FactorDslLimitError(
                code="ast_too_deep",
                message=f"AST depth exceeds maximum of {self.limits.max_ast_depth}",
                offset=self._current().offset,
                line=self._current().line,
                column=self._current().column,
            )

    def parse(self) -> AstNode:
        node = self._parse_expr(depth=1)
        if self._current().kind != TokenKind.EOF:
            raise self._parse_error("trailing_tokens", "unexpected tokens after expression")
        return node

    def _parse_expr(self, *, depth: int) -> AstNode:
        return self._parse_primary(depth=depth)

    def _parse_primary(self, *, depth: int) -> AstNode:
        tok = self._current()
        if tok.kind == TokenKind.NUMBER:
            self._advance()
            self._bump_node(depth)
            if "." in tok.value:
                value = float(tok.value)
            else:
                value = float(int(tok.value))
            if not math.isfinite(value):
                raise self._parse_error("non_finite_number", "non-finite numeric literals are not allowed", tok)
            return ConstantNode(value=value)

        if tok.kind == TokenKind.IDENT:
            name = tok.value
            if name in _UNSUPPORTED_OPS:
                raise self._parse_error("unsupported_feature", f"{name}() is not supported in {self.dsl_version}", tok)
            next_tok = self.tokens[self.pos + 1] if self.pos + 1 < len(self.tokens) else None
            if next_tok and next_tok.kind == TokenKind.LPAREN:
                return self._parse_call(name, depth=depth)
            if not FIELD_ID_PATTERN.match(name):
                raise self._parse_error("invalid_field_id", f"invalid field identifier: {name}", tok)
            if name in _FORBIDDEN_FIELD_IDENTS:
                raise self._parse_error("non_finite_number", "non-finite numeric literals are not allowed", tok)
            self._advance()
            self._bump_node(depth)
            return FieldNode(field_id=name)

        raise self._parse_error("expected_expression", "expected expression")

    def _parse_call(self, name: str, *, depth: int) -> AstNode:
        start = self._current()
        self._advance()  # ident
        self._expect(TokenKind.LPAREN)
        args = self._parse_args(depth=depth)
        self._expect(TokenKind.RPAREN)

        if name in _UNARY_OPS:
            return self._build_unary(name, args, start, depth)
        if name in _BINARY_OPS:
            return self._build_binary(name, args, start, depth)
        if name in _LAG_OPS or name in _ROLLING_OPS:
            return self._build_rolling(name, args, start, depth)
        if name in _CROSS_OPS:
            return self._build_cross(name, args, start, depth)
        if name in _NEUTRALIZE_OPS:
            return self._build_neutralize(name, args, start, depth)
        raise self._parse_error("unknown_function", f"unknown function: {name}", start)

    def _parse_args(self, *, depth: int) -> list[_Arg]:
        args: list[_Arg] = []
        if self._current().kind == TokenKind.RPAREN:
            return args
        while True:
            if self._current().kind == TokenKind.IDENT and self.tokens[self.pos + 1].kind == TokenKind.EQ:
                kw = self._advance().value
                if any(a.keyword == kw for a in args):
                    raise self._parse_error("duplicate_keyword", f"duplicate keyword argument: {kw}")
                self._advance()  # =
                val_tok = self._current()
                if val_tok.kind == TokenKind.STRING:
                    self._advance()
                    args.append(_Arg(keyword=kw, kw_value=val_tok.value))
                elif val_tok.kind == TokenKind.NUMBER:
                    self._advance()
                    args.append(_Arg(keyword=kw, kw_value=self._number_value(val_tok)))
                else:
                    raise self._parse_error("expected_kw_value", "keyword argument value must be string or number", val_tok)
            else:
                if any(a.keyword for a in args):
                    raise self._parse_error("positional_after_keyword", "positional argument after keyword argument")
                expr = self._parse_expr(depth=depth + 1)
                args.append(_Arg(positional=expr))
            if self._current().kind == TokenKind.COMMA:
                self._advance()
                if self._current().kind == TokenKind.RPAREN:
                    raise self._parse_error("trailing_comma", "trailing comma is not allowed")
                continue
            break
        return args

    def _number_value(self, tok: Token) -> float:
        if "." in tok.value:
            return float(tok.value)
        return float(int(tok.value))

    def _positional(self, args: list[_Arg], index: int, *, fn: str, start: Token) -> AstNode:
        pos = [a for a in args if a.positional is not None]
        if index >= len(pos):
            raise self._parse_error("missing_argument", f"{fn}() missing required positional argument {index + 1}", start)
        assert pos[index].positional is not None
        return pos[index].positional

    def _kw_string(self, args: list[_Arg], key: str, *, allowed: set[str], default: str) -> str:
        matches = [a for a in args if a.keyword == key]
        if not matches:
            return default
        if len(matches) > 1:
            raise FactorDslParseError(code="duplicate_keyword", message=f"duplicate keyword argument: {key}")
        val = matches[0].kw_value
        if not isinstance(val, str):
            raise FactorDslParseError(code="invalid_kw_type", message=f"{key} must be a string")
        if val not in allowed:
            raise FactorDslParseError(code="invalid_kw_value", message=f"invalid value for {key}: {val!r}")
        return val

    def _kw_float(self, args: list[_Arg], key: str, *, default: float) -> float:
        matches = [a for a in args if a.keyword == key]
        if not matches:
            return default
        if len(matches) > 1:
            raise FactorDslParseError(code="duplicate_keyword", message=f"duplicate keyword argument: {key}")
        val = matches[0].kw_value
        if isinstance(val, str):
            raise FactorDslParseError(code="invalid_kw_type", message=f"{key} must be a number")
        assert isinstance(val, float)
        return val

    def _reject_unknown_kw(self, args: list[_Arg], allowed: set[str]) -> None:
        for a in args:
            if a.keyword and a.keyword not in allowed:
                raise FactorDslParseError(code="unknown_keyword", message=f"unknown keyword argument: {a.keyword}")

    def _build_unary(self, name: str, args: list[_Arg], start: Token, depth: int) -> AstNode:
        allowed_kw = {"invalid_policy"} if name == "log" else set()
        self._reject_unknown_kw(args, allowed_kw)
        pos = [a for a in args if a.positional is not None]
        if len(pos) != 1:
            raise self._parse_error("invalid_arity", f"{name}() requires exactly 1 argument", start)
        child = pos[0].positional
        assert child is not None
        self._bump_node(depth)
        op_map = {
            "abs": UnaryOperator.ABS,
            "negate": UnaryOperator.NEGATE,
            "log": UnaryOperator.LOG,
            "sign": UnaryOperator.SIGN,
        }
        node = UnaryNode(op=op_map[name], child=child)
        if name == "log":
            policy = self._kw_string(
                args,
                "invalid_policy",
                allowed=set(_LOG_POLICY_MAP),
                default="null",
            )
            node = node.model_copy(update={"log_policy": _LOG_POLICY_MAP[policy]})
        return node

    def _build_binary(self, name: str, args: list[_Arg], start: Token, depth: int) -> AstNode:
        allowed_kw = {"zero_policy"} if name == "divide" else set()
        self._reject_unknown_kw(args, allowed_kw)
        pos = [a for a in args if a.positional is not None]
        if len(pos) != 2:
            raise self._parse_error("invalid_arity", f"{name}() requires exactly 2 arguments", start)
        left, right = pos[0].positional, pos[1].positional
        assert left is not None and right is not None
        self._bump_node(depth)
        zero_policy = ZeroDivisionPolicy.NULL
        if name == "divide":
            z = self._kw_string(args, "zero_policy", allowed=set(_ZERO_POLICY_MAP), default="null")
            zero_policy = _ZERO_POLICY_MAP[z]
        return BinaryNode(op=_DSL_TO_BINARY[name], left=left, right=right, zero_policy=zero_policy)

    def _parse_positive_int(self, value: float, *, field: str, start: Token, max_value: int) -> int:
        if value != int(value) or value <= 0:
            raise self._parse_error("invalid_window", f"{field} must be a positive integer", start)
        iv = int(value)
        if iv > max_value:
            raise FactorDslLimitError(
                code="window_too_large",
                message=f"{field} exceeds maximum of {max_value}",
                offset=start.offset,
                line=start.line,
                column=start.column,
            )
        return iv

    def _build_rolling(self, name: str, args: list[_Arg], start: Token, depth: int) -> AstNode:
        self._reject_unknown_kw(args, set())
        op = _DSL_TO_ROLLING[name]
        pos = [a for a in args if a.positional is not None]
        if op == RollingOperator.ROLLING_CORRELATION:
            if len(pos) != 3:
                raise self._parse_error("invalid_arity", "rolling_correlation() requires exactly 3 arguments", start)
            left, right, window_arg = pos[0].positional, pos[1].positional, pos[2].positional
            assert left is not None and right is not None
            if not isinstance(window_arg, ConstantNode):
                raise self._parse_error("invalid_window", "rolling_correlation window must be an integer literal", start)
            window = self._parse_positive_int(
                window_arg.value,
                field="window",
                start=start,
                max_value=self.limits.max_rolling_window,
            )
            self._bump_node(depth)
            return RollingNode(op=op, child=left, right=right, window=window)

        if len(pos) != 2:
            raise self._parse_error("invalid_arity", f"{name}() requires exactly 2 arguments", start)
        child, period_arg = pos[0].positional, pos[1].positional
        assert child is not None
        if not isinstance(period_arg, ConstantNode):
            raise self._parse_error("invalid_window", f"{name} periods/window must be an integer literal", start)
        max_val = self.limits.max_lag_periods if name in _LAG_OPS else self.limits.max_rolling_window
        field = "periods" if name in _LAG_OPS else "window"
        window = self._parse_positive_int(period_arg.value, field=field, start=start, max_value=max_val)
        self._bump_node(depth)
        return RollingNode(op=op, child=child, window=window)

    def _build_cross(self, name: str, args: list[_Arg], start: Token, depth: int) -> AstNode:
        allowed_kw = {"lower", "upper"} if name == "winsorize" else set()
        self._reject_unknown_kw(args, allowed_kw)
        pos = [a for a in args if a.positional is not None]
        if len(pos) != 1:
            raise self._parse_error("invalid_arity", f"{name}() requires exactly 1 argument", start)
        child = pos[0].positional
        assert child is not None
        self._bump_node(depth)
        lower = self._kw_float(args, "lower", default=0.01)
        upper = self._kw_float(args, "upper", default=0.99)
        if name == "winsorize":
            if not (0 <= lower < upper <= 1):
                raise self._parse_error("invalid_winsorize", "winsorize requires 0 <= lower < upper <= 1", start)
        return CrossSectionNode(
            op=_DSL_TO_CROSS[name],
            child=child,
            winsorize_lower=lower,
            winsorize_upper=upper,
        )

    def _build_neutralize(self, name: str, args: list[_Arg], start: Token, depth: int) -> AstNode:
        self._reject_unknown_kw(args, set())
        pos = [a for a in args if a.positional is not None]
        if len(pos) != 1:
            raise self._parse_error("invalid_arity", f"{name}() requires exactly 1 argument", start)
        child = pos[0].positional
        assert child is not None
        self._bump_node(depth)
        return NeutralizeNode(key=_NEUTRALIZE_OPS[name], child=child)


def parse_factor_expression(
    source: str,
    *,
    dsl_version: str = FACTOR_DSL_V1,
    limits: FactorDslLimits | None = None,
) -> AstNode:
    """Parse a factor DSL expression into a validated AST."""
    if dsl_version != FACTOR_DSL_V1:
        raise FactorDslParseError(
            code="unsupported_dsl_version",
            message=f"unsupported DSL version: {dsl_version}",
            offset=0,
            line=1,
            column=1,
        )
    lim = limits or FactorDslLimits()
    tokens = tokenize(source, limits=lim)
    parser = _Parser(tokens, limits=lim, dsl_version=dsl_version)
    node = parser.parse()
    return node
