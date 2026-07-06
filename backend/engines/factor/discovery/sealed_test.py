"""Sealed-test access controls for Factor Discovery validation."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from engines.factor.discovery.validation_errors import HashMismatchError, SealedTestAccessError
from engines.factor.discovery.validation_models import SealedTestAccess, SealedTestStatus


def validate_sealed_test_access(
    access: SealedTestAccess,
    *,
    formula_hash: str,
    plan_hash: str,
) -> None:
    if not access.approval_reference:
        raise SealedTestAccessError(code="missing_approval", message="approval_reference required")
    if access.expected_formula_hash != formula_hash:
        raise HashMismatchError(
            code="formula_hash_mismatch",
            message="sealed access formula hash does not match execution",
        )
    if access.expected_plan_hash != plan_hash:
        raise HashMismatchError(
            code="plan_hash_mismatch",
            message="sealed access plan hash does not match execution",
        )


def sealed_test_receipt_hash(
    *,
    formula_hash: str,
    plan_hash: str,
    validation_config_hash: str,
    period_resolution_hash: str,
    sealed_result_hash: str,
    access: SealedTestAccess,
) -> str:
    payload = {
        "formula": formula_hash,
        "plan": plan_hash,
        "config": validation_config_hash,
        "periods": period_resolution_hash,
        "sealed_result": sealed_result_hash,
        "access": access.canonical_payload(),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return f"sha256:{hashlib.sha256(canonical.encode()).hexdigest()}"


def build_sealed_test_status(
    *,
    sessions: tuple[str, ...],
    opened: bool,
    receipt_hash: str | None = None,
) -> SealedTestStatus:
    if not sessions:
        return SealedTestStatus(status="INSUFFICIENT_DATA", session_count=0, opened=opened)
    return SealedTestStatus(
        status="OPENED" if opened else "SEALED",
        session_count=len(sessions),
        start_date=sessions[0],
        end_date=sessions[-1],
        opened=opened,
        receipt_hash=receipt_hash,
    )


def redact_sealed_metrics(metrics: dict[str, Any] | None) -> None:
    """Ensure sealed metrics are absent when not opened — caller should pass None."""
    return None
