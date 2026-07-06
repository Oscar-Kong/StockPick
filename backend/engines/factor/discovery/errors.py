"""Typed errors for Factor Discovery DSL parsing and compilation."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FactorDslError(Exception):
    code: str
    message: str
    offset: int | None = None
    line: int | None = None
    column: int | None = None
    token: str | None = None
    context: str | None = None

    def __str__(self) -> str:
        parts = [f"[{self.code}] {self.message}"]
        if self.line is not None and self.column is not None:
            parts.append(f"at line {self.line}, column {self.column}")
        elif self.offset is not None:
            parts.append(f"at offset {self.offset}")
        if self.token:
            parts.append(f"near {self.token!r}")
        if self.context:
            parts.append(f"({self.context})")
        return " ".join(parts)


class FactorDslTokenizationError(FactorDslError):
    pass


class FactorDslParseError(FactorDslError):
    pass


class FactorDslLimitError(FactorDslError):
    pass


class FactorCompileError(FactorDslError):
    pass


class UnknownOperatorError(FactorCompileError):
    pass


class UnknownFieldError(FactorCompileError):
    pass


class ForbiddenFieldError(FactorCompileError):
    pass


class UnsupportedNodeError(FactorCompileError):
    pass


class InvalidOperatorArgumentsError(FactorCompileError):
    pass
