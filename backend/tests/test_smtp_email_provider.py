"""Tests for SMTP email provider."""
from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

from services.email.smtp_provider import SmtpEmailProvider, _send_smtp_message
from services.scan_email_config import extract_email_address


def test_extract_email_address_parses_display_name():
    assert extract_email_address("StockPick <ops@gmail.com>") == "ops@gmail.com"
    assert extract_email_address("ops@gmail.com") == "ops@gmail.com"


def test_send_smtp_message_uses_ssl_on_port_465():
    server = MagicMock()
    server.sendmail.return_value = {}
    with patch("services.email.smtp_provider.smtplib.SMTP_SSL") as ssl_cls:
        ssl_cls.return_value.__enter__.return_value = server
        _send_smtp_message(
            host="smtp.163.com",
            port=465,
            user="u@163.com",
            password="secret",
            use_tls=True,
            from_address="StockPick <u@163.com>",
            to=["dest@example.com"],
            subject="Test",
            html="<p>Hi</p>",
            text="Hi",
            timeout=5.0,
        )
    ssl_cls.assert_called_once()
    server.login.assert_called_once()
    server.sendmail.assert_called_once()


def test_send_smtp_message_uses_bare_envelope_sender():
    server = MagicMock()
    server.sendmail.return_value = {}
    with patch("services.email.smtp_provider.smtplib.SMTP") as smtp_cls:
        smtp_cls.return_value.__enter__.return_value = server
        _send_smtp_message(
            host="smtp.gmail.com",
            port=587,
            user="u@gmail.com",
            password="secret",
            use_tls=True,
            from_address="StockPick <u@gmail.com>",
            to=["dest@example.com"],
            subject="Test",
            html="<p>Hi</p>",
            text="Hi",
            timeout=5.0,
        )
    server.sendmail.assert_called_once()
    assert server.sendmail.call_args.args[0] == "u@gmail.com"
    assert server.sendmail.call_args.args[1] == ["dest@example.com"]


def test_smtp_missing_credentials(monkeypatch):
    monkeypatch.setattr("services.email.smtp_provider.SMTP_USER", "")
    monkeypatch.setattr("services.email.smtp_provider.SMTP_PASSWORD", "")
    monkeypatch.setattr("config.SMTP_FALLBACK_USER", "")
    monkeypatch.setattr("config.SMTP_FALLBACK_PASSWORD", "")
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


def test_smtp_fallback_on_primary_timeout(monkeypatch):
    import smtplib

    monkeypatch.setattr("config.SMTP_FALLBACK_HOST", "smtp.gmail.com")
    monkeypatch.setattr("config.SMTP_FALLBACK_PORT", 587)
    monkeypatch.setattr("config.SMTP_FALLBACK_USER", "fallback@gmail.com")
    monkeypatch.setattr("config.SMTP_FALLBACK_PASSWORD", "app-pass")
    monkeypatch.setattr("config.SMTP_FALLBACK_USE_TLS", True)
    monkeypatch.setattr("config.SCAN_EMAIL_FROM_FALLBACK", "StockPick <fallback@gmail.com>")

    provider = SmtpEmailProvider(user="primary@163.com", password="code", host="smtp.163.com", port=465)
    with patch(
        "services.email.smtp_provider._send_smtp_message",
        side_effect=[TimeoutError("timed out"), "smtp-fallback123"],
    ) as send:
        result = asyncio.run(
            provider.send_email(
                to=["dest@example.com"],
                subject="Test",
                html="<p>x</p>",
                text="x",
                from_address="StockPick <primary@163.com>",
            )
        )
    assert result.ok is True
    assert result.provider == "smtp_fallback"
    assert result.message_id == "smtp-fallback123"
    assert send.call_count == 2
    assert send.call_args_list[1].kwargs["host"] == "smtp.gmail.com"
    assert send.call_args_list[1].kwargs["from_address"] == "StockPick <fallback@gmail.com>"
