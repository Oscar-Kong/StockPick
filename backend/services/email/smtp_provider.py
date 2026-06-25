"""SMTP email provider (Gmail and other SMTP servers)."""
from __future__ import annotations

import asyncio
import logging
import smtplib
import uuid
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config import SMTP_HOST, SMTP_PASSWORD, SMTP_PORT, SMTP_USE_TLS, SMTP_USER
from services.email.types import EmailDeliveryResult

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30.0


def _send_smtp_message(
    *,
    host: str,
    port: int,
    user: str,
    password: str,
    use_tls: bool,
    from_address: str,
    to: list[str],
    subject: str,
    html: str,
    text: str,
    timeout: float,
) -> str:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_address
    msg["To"] = ", ".join(to)
    msg.attach(MIMEText(text, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    with smtplib.SMTP(host=host, port=port, timeout=timeout) as server:
        server.ehlo()
        if use_tls:
            server.starttls()
            server.ehlo()
        if user:
            server.login(user, password)
        refused = server.sendmail(from_address, to, msg.as_string())
        if refused:
            raise smtplib.SMTPRecipientsRefused(refused)
    return f"smtp-{uuid.uuid4().hex[:12]}"


def _format_smtp_error(exc: Exception) -> tuple[str, str]:
    if isinstance(exc, smtplib.SMTPAuthenticationError):
        return (
            "smtp_auth_failed",
            "SMTP authentication failed — for Gmail use an App Password (not your login password). "
            "See https://myaccount.google.com/apppasswords",
        )
    if isinstance(exc, smtplib.SMTPRecipientsRefused):
        return ("smtp_recipient_refused", "SMTP server refused one or more recipients")
    if isinstance(exc, smtplib.SMTPException):
        return ("smtp_error", str(exc)[:200])
    if isinstance(exc, TimeoutError):
        return ("timeout", "SMTP connection timed out")
    return ("network_error", str(exc)[:200])


class SmtpEmailProvider:
    def __init__(
        self,
        *,
        host: str | None = None,
        port: int | None = None,
        user: str | None = None,
        password: str | None = None,
        use_tls: bool | None = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self.host = (host or SMTP_HOST or "smtp.gmail.com").strip()
        self.port = int(port if port is not None else SMTP_PORT)
        self.user = (user or SMTP_USER or "").strip()
        self.password = (password or SMTP_PASSWORD or "").strip()
        self.use_tls = SMTP_USE_TLS if use_tls is None else use_tls
        self.timeout = timeout

    async def send_email(
        self,
        *,
        to: list[str],
        subject: str,
        html: str,
        text: str,
        from_address: str,
    ) -> EmailDeliveryResult:
        if not self.user or not self.password:
            return EmailDeliveryResult(
                ok=False,
                provider="smtp",
                error_code="missing_smtp_credentials",
                error_summary="SMTP_USER and SMTP_PASSWORD are required when SCAN_EMAIL_PROVIDER=smtp",
            )
        if not to:
            return EmailDeliveryResult(
                ok=False,
                provider="smtp",
                error_code="missing_recipient",
                error_summary="No recipients configured",
            )

        try:
            message_id = await asyncio.to_thread(
                _send_smtp_message,
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                use_tls=self.use_tls,
                from_address=from_address,
                to=to,
                subject=subject,
                html=html,
                text=text,
                timeout=self.timeout,
            )
            return EmailDeliveryResult(ok=True, provider="smtp", message_id=message_id)
        except Exception as exc:
            code, summary = _format_smtp_error(exc)
            logger.warning("SMTP email failed: %s", code)
            return EmailDeliveryResult(
                ok=False,
                provider="smtp",
                error_code=code,
                error_summary=summary,
            )
