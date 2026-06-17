"""Structured portfolio API error payloads."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi import HTTPException

from utils.api_errors import detail_message, portfolio_error


def test_portfolio_error_shape():
    exc = portfolio_error(
        code="PORTFOLIO_OPTIMIZATION_FAILED",
        message="The allocation could not be calculated.",
        status_code=400,
        retryable=True,
    )
    assert isinstance(exc, HTTPException)
    assert exc.status_code == 400
    detail = exc.detail
    assert detail["error"] == "PORTFOLIO_OPTIMIZATION_FAILED"
    assert detail["message"] == "The allocation could not be calculated."
    assert detail["retryable"] is True
    assert detail["request_id"].startswith("req_")


def test_detail_message_from_structured_detail():
    msg = detail_message({"error": "X", "message": "Human readable"})
    assert msg == "Human readable"
