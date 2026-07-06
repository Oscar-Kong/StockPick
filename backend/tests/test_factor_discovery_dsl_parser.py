"""Tests for Factor Discovery DSL tokenizer and parser."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from pydantic import TypeAdapter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engines.factor.discovery.errors import FactorDslLimitError, FactorDslParseError, FactorDslTokenizationError
from engines.factor.discovery.formatter import format_factor_expression
from engines.factor.discovery.limits import FactorDslLimits
from engines.factor.discovery.parser import parse_factor_expression
from engines.factor.discovery.tokenizer import TokenKind, tokenize
from models.schemas_factor_discovery import AstNode, formula_hash

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "factor_discovery"
AST_ADAPTER = TypeAdapter(AstNode)


def _load_ast(name: str) -> AstNode:
    raw = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return AST_ADAPTER.validate_python(raw)


def _load_dsl(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8").strip()


# --- Tokenizer ---


def test_tokenizer_identifiers_and_punctuation():
    toks = tokenize("rank(x)")
    kinds = [t.kind for t in toks if t.kind != TokenKind.EOF]
    assert kinds == [TokenKind.IDENT, TokenKind.LPAREN, TokenKind.IDENT, TokenKind.RPAREN]


def test_tokenizer_number_and_string():
    toks = tokenize('divide(a,b,zero_policy="null")')
    assert any(t.kind == TokenKind.STRING and t.value == "null" for t in toks)


def test_tokenizer_tracks_line_column():
    toks = tokenize("rank(\n  x\n)")
    rank = next(t for t in toks if t.value == "rank")
    assert rank.line == 1
    x = next(t for t in toks if t.value == "x")
    assert x.line == 2


def test_tokenizer_rejects_invalid_character():
    with pytest.raises(FactorDslTokenizationError):
        tokenize("a + b")


def test_tokenizer_rejects_unterminated_string():
    with pytest.raises(FactorDslTokenizationError):
        tokenize('"oops')


def test_tokenizer_rejects_non_finite_number():
    with pytest.raises(FactorDslParseError):
        parse_factor_expression("rank(nan)")


def test_tokenizer_rejects_scientific_notation():
    with pytest.raises(FactorDslTokenizationError):
        tokenize("1e6")


def test_tokenizer_source_length_limit():
    with pytest.raises(FactorDslLimitError):
        tokenize("x" * 20_000, limits=FactorDslLimits(max_source_length=100))


# --- Parser success ---


def _substitute_fields(dsl: str) -> str:
    return (
        dsl.replace("FIELD_X", "return_126d")
        .replace("FIELD_A", "return_1d")
        .replace("FIELD_B", "relative_volume")
    )


@pytest.mark.parametrize(
    "dsl",
    [
        "abs(FIELD_X)",
        "negate(FIELD_X)",
        'log(FIELD_X,invalid_policy="null")',
        "sign(FIELD_X)",
        "add(FIELD_A,FIELD_B)",
        "subtract(FIELD_A,FIELD_B)",
        "multiply(FIELD_A,FIELD_B)",
        'divide(FIELD_A,FIELD_B,zero_policy="null")',
        "min(FIELD_A,FIELD_B)",
        "max(FIELD_A,FIELD_B)",
        "lag(FIELD_X,1)",
        "delta(FIELD_X,5)",
        "pct_change(FIELD_X,21)",
        "rolling_mean(FIELD_X,20)",
        "rolling_std(FIELD_X,20)",
        "rolling_min(FIELD_X,20)",
        "rolling_max(FIELD_X,20)",
        "rolling_sum(FIELD_X,20)",
        "rolling_correlation(FIELD_A,FIELD_B,20)",
        "rank(FIELD_X)",
        "percentile_rank(FIELD_X)",
        "zscore(FIELD_X)",
        "winsorize(FIELD_X,lower=0.01,upper=0.99)",
        "sector_neutralize(FIELD_X)",
        "industry_neutralize(FIELD_X)",
        "market_cap_neutralize(FIELD_X)",
    ],
)
def test_parser_supports_operators(dsl):
    node = parse_factor_expression(_substitute_fields(dsl))
    assert node is not None


def test_parser_nested_and_multiline():
    src = """
    add(
        multiply(0.4, rank(return_126d)),
        multiply(0.6, rank(return_1d))
    )
    """
    node = parse_factor_expression(src)
    assert formula_hash(node).startswith("sha256:")


@pytest.mark.parametrize(
    "json_name,dsl_name",
    [
        ("simple_field_rank.json", "simple_field_rank.dsl"),
        ("lagged_momentum.json", "lagged_momentum.dsl"),
        ("safe_division_fcf_mcap.json", "safe_division_fcf_mcap.dsl"),
        ("sector_neutral_composite.json", "sector_neutral_composite.dsl"),
        ("nested_rolling.json", "nested_rolling.dsl"),
    ],
)
def test_golden_dsl_matches_json_hash(json_name, dsl_name):
    expected = formula_hash(_load_ast(json_name))
    parsed = parse_factor_expression(_load_dsl(dsl_name))
    assert formula_hash(parsed) == expected


@pytest.mark.parametrize(
    "json_name",
    [
        "simple_field_rank.json",
        "lagged_momentum.json",
        "safe_division_fcf_mcap.json",
        "sector_neutral_composite.json",
        "nested_rolling.json",
    ],
)
def test_json_format_parse_round_trip(json_name):
    ast = _load_ast(json_name)
    dsl = format_factor_expression(ast)
    reparsed = parse_factor_expression(dsl)
    assert formula_hash(reparsed) == formula_hash(ast)


# --- Parser rejection ---


@pytest.mark.parametrize(
    "src,code_fragment",
    [
        ('__import__("os")', "forbidden"),
        ("obj.field", "invalid"),
        ("FIELD_X[0]", "invalid"),
        ("FIELD_A + FIELD_B", "invalid"),
        ("FIELD_A / FIELD_B", "invalid"),
        ("lambda x: x", "invalid"),
        ('eval("x")', "expected"),
        ('open("/tmp/x")', "expected"),
        ("rank()", "arity"),
        ("rank(FIELD_A,FIELD_B)", "arity"),
        ('divide(FIELD_A,FIELD_B,bad_policy="x")', "unknown"),
        ("lag(FIELD_A,-1)", "invalid"),
        ("lag(FIELD_A,1.5)", "integer"),
        ("rolling_mean(FIELD_A,0)", "positive"),
        ("rolling_correlation(FIELD_A,21)", "arity"),
        ("rolling_correlation(FIELD_A,FIELD_B,0)", "positive"),
        ("winsorize(FIELD_A,lower=0.9,upper=0.1)", "winsorize"),
        ("unknown_function(FIELD_A)", "unknown"),
        ("rank(FIELD_A) trailing", "trailing"),
        ("rank(FIELD_A,extra=1)", "unknown"),
        ("rank(FIELD_A,extra=1,extra=2)", "duplicate"),
        ('rank(FIELD_A,zero_policy="null",FIELD_B)', "positional_after_keyword"),
        ("where(FIELD_A,FIELD_B,FIELD_X)", "unsupported"),
        ("_secret", "forbidden"),
    ],
)
def test_parser_rejects_malformed(src, code_fragment):
    src = _substitute_fields(src)
    with pytest.raises((FactorDslParseError, FactorDslTokenizationError, FactorDslLimitError)) as exc:
        parse_factor_expression(src)
    assert code_fragment in exc.value.code or code_fragment in str(exc.value).lower()


def test_parser_max_depth_limit():
    inner = "return_126d"
    for _ in range(40):
        inner = f"abs({inner})"
    with pytest.raises(FactorDslLimitError):
        parse_factor_expression(inner, limits=FactorDslLimits(max_ast_depth=8))


def test_parser_max_nodes_limit():
    parts = ["rank(return_126d)"] * 300
    src = "add(" + ",".join(parts) + ")"
    with pytest.raises(FactorDslLimitError):
        parse_factor_expression(src, limits=FactorDslLimits(max_ast_nodes=16))


def test_parser_excessive_rolling_window():
    with pytest.raises(FactorDslLimitError):
        parse_factor_expression("rolling_mean(return_126d,3000)")


# --- Property-style combinations ---


@pytest.mark.parametrize(
    "dsl",
    [
        "rank(negate(return_126d))",
        "rolling_mean(multiply(return_1d,0.5),10)",
        "sector_neutralize(zscore(rolling_mean(return_1d,5)))",
        'divide(return_1d,return_126d,zero_policy="epsilon")',
        'log(return_126d,invalid_policy="abs_log")',
        "rolling_mean(return_126d,2520)",
        "lag(return_126d,2520)",
    ],
)
def test_parser_parameterized_combinations(dsl):
    node = parse_factor_expression(dsl)
    assert formula_hash(node).startswith("sha256:")
