"""Tests for SMTP email provider."""
from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

from services.email.smtp_provider import SmtpEmailProvider


def test_smtp_missing_credentials():
    provider = SmtpEmailProvider(user="", password="")
    result = asyncio.run(
        provider.send_email(
            to=["a@example.com"],
            subject="Test",
            html="<p>Hi</p>",
            text="Hi",
            from_address="StockPick <a@example.com>",
        )
    )
    assert result.ok is False
    assert result.error_code == "missing_smtp_credentials"


def test_smtp_send_success():
    provider = SmtpEmailProvider(user="u@gmail.com", password="app-pass")
    with patch("services.email.smtp_provider._send_smtp_message", return_value="smtp-abc123") as send:
        result = asyncio.run(
            provider.send_email(
                to=["dest@example.com"],
                subject="Morning Scan",
                html="<p>Scan</p>",
                text="Scan",
                from_address="StockPick <u@gmail.com>",
            )
        )
    assert result.ok is True
    assert result.provider == "smtp"
    assert result.message_id == "smtp-abc123"
    send.assert_called_once()


def test_smtp_auth_error_message():
    import smtplib

    provider = SmtpEmailProvider(user="u@gmail.com", password="bad")
    with patch(
        "services.email.smtp_provider._send_smtp_message",
        side_effect=smtplib.SMTPAuthenticationError(535, b"Auth failed"),
    ):
        result = asyncio.run(
            provider.send_email(
                to=["dest@example.com"],
                subject="Test",
                html="<p>x</p>",
                text="x",
                from_address="StockPick <u@gmail.com>",
            )
        )
    assert result.ok is False
    assert result.error_code == "smtp_auth_failed"
    assert "App Password" in (result.error_summary or "")
