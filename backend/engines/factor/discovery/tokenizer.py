"""Character-level tokenizer for factor-dsl-v1."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterator

from .errors import FactorDslLimitError, FactorDslTokenizationError
from .limits import FactorDslLimits


class TokenKind(str, Enum):
    IDENT = "IDENT"
    NUMBER = "NUMBER"
    STRING = "STRING"
    LPAREN = "LPAREN"
    RPAREN = "RPAREN"
    COMMA = "COMMA"
    EQ = "EQ"
    EOF = "EOF"


@dataclass(frozen=True)
class Token:
    kind: TokenKind
    value: str
    offset: int
    line: int
    column: int


def _is_ident_start(ch: str) -> bool:
    return "a" <= ch <= "z" or ch == "_"


def _is_ident_continue(ch: str) -> bool:
    return _is_ident_start(ch) or ("0" <= ch <= "9")


def tokenize(source: str, *, limits: FactorDslLimits | None = None) -> list[Token]:
    """Tokenize DSL source into a bounded token stream."""
    lim = limits or FactorDslLimits()
    if len(source) > lim.max_source_length:
        raise FactorDslLimitError(
            code="source_too_long",
            message=f"source exceeds maximum length of {lim.max_source_length}",
            offset=lim.max_source_length,
        )

    tokens: list[Token] = []
    i = 0
    line = 1
    column = 1
    n = len(source)

    def _err(code: str, message: str, *, offset: int, line: int, column: int) -> FactorDslTokenizationError:
        return FactorDslTokenizationError(
            code=code,
            message=message,
            offset=offset,
            line=line,
            column=column,
        )

    def _append(tok: Token) -> None:
        if len(tokens) >= lim.max_tokens:
            raise FactorDslLimitError(
                code="too_many_tokens",
                message=f"token count exceeds maximum of {lim.max_tokens}",
                offset=tok.offset,
                line=tok.line,
                column=tok.column,
            )
        tokens.append(tok)

    while i < n:
        ch = source[i]
        if ch in " \t\r\n":
            if ch == "\n":
                line += 1
                column = 0
            i += 1
            column += 1
            continue
        start_offset = i
        start_line = line
        start_col = column

        if ch == "(":
            _append(Token(TokenKind.LPAREN, "(", start_offset, start_line, start_col))
            i += 1
            column += 1
            continue
        if ch == ")":
            _append(Token(TokenKind.RPAREN, ")", start_offset, start_line, start_col))
            i += 1
            column += 1
            continue
        if ch == ",":
            _append(Token(TokenKind.COMMA, ",", start_offset, start_line, start_col))
            i += 1
            column += 1
            continue
        if ch == "=":
            _append(Token(TokenKind.EQ, "=", start_offset, start_line, start_col))
            i += 1
            column += 1
            continue

        if ch == '"':
            i += 1
            column += 1
            buf: list[str] = []
            while i < n and source[i] != '"':
                if source[i] == "\\":
                    i += 1
                    column += 1
                    if i >= n:
                        raise _err("unterminated_string", "unterminated string literal", offset=start_offset, line=start_line, column=start_col)
                    esc = source[i]
                    if esc == "n":
                        buf.append("\n")
                    elif esc == "t":
                        buf.append("\t")
                    elif esc == "\\":
                        buf.append("\\")
                    elif esc == '"':
                        buf.append('"')
                    else:
                        raise _err("invalid_escape", f"invalid escape sequence \\{esc}", offset=i, line=line, column=column)
                    i += 1
                    column += 1
                    continue
                if source[i] == "\n":
                    raise _err("unterminated_string", "unterminated string literal", offset=start_offset, line=start_line, column=start_col)
                buf.append(source[i])
                i += 1
                column += 1
            if i >= n:
                raise _err("unterminated_string", "unterminated string literal", offset=start_offset, line=start_line, column=start_col)
            i += 1
            column += 1
            sval = "".join(buf)
            _append(Token(TokenKind.STRING, sval, start_offset, start_line, start_col))
            continue

        if ch.isdigit() or (ch == "." and i + 1 < n and source[i + 1].isdigit()):
            j = i
            col_j = column
            if source[j] == "-":
                raise _err("invalid_character", "unary minus is not allowed; use negate()", offset=j, line=line, column=col_j)
            while j < n and source[j].isdigit():
                j += 1
            if j < n and source[j] == ".":
                j += 1
                while j < n and source[j].isdigit():
                    j += 1
            if j < n and source[j] in "eE":
                raise _err("scientific_notation", "scientific notation is not allowed", offset=j, line=line, column=column + (j - i))
            literal = source[i:j]
            if len(literal) > lim.max_numeric_literal_length:
                raise FactorDslLimitError(
                    code="numeric_literal_too_long",
                    message=f"numeric literal exceeds maximum length of {lim.max_numeric_literal_length}",
                    offset=start_offset,
                    line=start_line,
                    column=start_col,
                )
            try:
                if "." in literal:
                    val = float(literal)
                else:
                    val = float(int(literal))
            except ValueError as exc:
                raise _err("invalid_number", "invalid numeric literal", offset=start_offset, line=start_line, column=start_col) from exc
            if val != val or val in (float("inf"), float("-inf")):
                raise _err("non_finite_number", "non-finite numeric literals are not allowed", offset=start_offset, line=start_line, column=start_col)
            _append(Token(TokenKind.NUMBER, literal, start_offset, start_line, start_col))
            column += j - i
            i = j
            continue

        if _is_ident_start(ch):
            j = i
            while j < n and _is_ident_continue(source[j]):
                j += 1
            ident = source[i:j]
            if len(ident) > lim.max_identifier_length:
                raise FactorDslLimitError(
                    code="identifier_too_long",
                    message=f"identifier exceeds maximum length of {lim.max_identifier_length}",
                    offset=start_offset,
                    line=start_line,
                    column=start_col,
                    token=ident[:32],
                )
            if ident.startswith("_") or "__" in ident:
                raise _err("forbidden_identifier", "identifiers must not start with underscore or contain dunder", offset=start_offset, line=start_line, column=start_col, )
            if not ident[0].isalpha():
                raise _err("invalid_identifier", "identifier must start with a lowercase letter", offset=start_offset, line=start_line, column=start_col)
            _append(Token(TokenKind.IDENT, ident, start_offset, start_line, start_col))
            column += j - i
            i = j
            continue

        raise _err("invalid_character", f"invalid character {ch!r}", offset=start_offset, line=start_line, column=start_col)

    _append(Token(TokenKind.EOF, "", i, line, column))
    return tokens


def iter_non_eof(tokens: list[Token]) -> Iterator[Token]:
    for tok in tokens:
        if tok.kind != TokenKind.EOF:
            yield tok
