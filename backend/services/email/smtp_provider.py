"""SMTP email provider (Gmail, 163, and other SMTP servers with optional fallback)."""
from __future__ import annotations

import asyncio
import logging
import smtplib
import uuid
from dataclasses import dataclass
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, parseaddr

from config import SMTP_HOST, SMTP_PASSWORD, SMTP_PORT, SMTP_USE_TLS, SMTP_USER
from services.email.types import EmailDeliveryResult
from services.scan_email_config import extract_email_address

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30.0


@dataclass(frozen=True)
class SmtpEndpoint:
    label: str
    host: str
    port: int
    user: str
    password: str
    use_tls: bool
    from_address: str


def _from_for_smtp_user(from_address: str, smtp_user: str, explicit: str = "") -> str:
    if explicit.strip():
        return explicit.strip()
    display_name, _ = parseaddr(from_address)
    if display_name:
        return formataddr((display_name, smtp_user))
    return smtp_user


def _fallback_endpoint(from_address: str) -> SmtpEndpoint | None:
    from config import (
        SCAN_EMAIL_FROM_FALLBACK,
        SMTP_FALLBACK_HOST,
        SMTP_FALLBACK_PASSWORD,
        SMTP_FALLBACK_PORT,
        SMTP_FALLBACK_USE_TLS,
        SMTP_FALLBACK_USER,
    )

    user = (SMTP_FALLBACK_USER or "").strip()
    password = (SMTP_FALLBACK_PASSWORD or "").strip()
    if not user or not password:
        return None
    host = (SMTP_FALLBACK_HOST or "smtp.gmail.com").strip()
    return SmtpEndpoint(
        label="smtp_fallback",
        host=host,
        port=int(SMTP_FALLBACK_PORT or 587),
        user=user,
        password=password,
        use_tls=SMTP_FALLBACK_USE_TLS,
        from_address=_from_for_smtp_user(from_address, user, SCAN_EMAIL_FROM_FALLBACK),
    )


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
    display_name, from_email = parseaddr(from_address)
    if not from_email:
        from_email = extract_email_address(from_address) or user
    msg["From"] = formataddr((display_name, from_email)) if display_name else from_email
    msg["To"] = ", ".join(to)
    msg.attach(MIMEText(text, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    if port == 465:
        smtp_factory = lambda: smtplib.SMTP_SSL(host=host, port=port, timeout=timeout)
    else:
        smtp_factory = lambda: smtplib.SMTP(host=host, port=port, timeout=timeout)

    with smtp_factory() as server:
        if port != 465:
            server.ehlo()
            if use_tls:
                server.starttls()
                server.ehlo()
        if user:
            server.login(user, password)
        refused = server.sendmail(from_email, to, msg.as_string())
        if refused:
            raise smtplib.SMTPRecipientsRefused(refused)
    return f"smtp-{uuid.uuid4().hex[:12]}"


def _format_smtp_error(exc: Exception) -> tuple[str, str]:
    if isinstance(exc, smtplib.SMTPAuthenticationError):
        return (
            "smtp_auth_failed",
            "SMTP authentication failed — use an App Password for Gmail, or the authorization code (授权码) for 163/QQ. "
            "Gmail: https://myaccount.google.com/apppasswords",
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

    def _endpoints(self, from_address: str) -> list[SmtpEndpoint]:
        endpoints: list[SmtpEndpoint] = []
        if self.user and self.password:
            endpoints.append(
                SmtpEndpoint(
                    label="smtp",
                    host=self.host,
                    port=self.port,
                    user=self.user,
                    password=self.password,
                    use_tls=self.use_tls,
                    from_address=from_address,
                )
            )
        fallback = _fallback_endpoint(from_address)
        if fallback is not None:
            endpoints.append(fallback)
        return endpoints

    async def send_email(
        self,
        *,
        to: list[str],
        subject: str,
        html: str,
        text: str,
        from_address: str,
    ) -> EmailDeliveryResult:
        if not to:
            return EmailDeliveryResult(
                ok=False,
                provider="smtp",
                error_code="missing_recipient",
                error_summary="No recipients configured",
            )

        endpoints = self._endpoints(from_address)
        if not endpoints:
            return EmailDeliveryResult(
                ok=False,
                provider="smtp",
                error_code="missing_smtp_credentials",
                error_summary="SMTP_USER and SMTP_PASSWORD are required when SCAN_EMAIL_PROVIDER=smtp",
            )

        last_code = "smtp_error"
        last_summary = "SMTP delivery failed"
        for index, endpoint in enumerate(endpoints):
            try:
                message_id = await asyncio.to_thread(
                    _send_smtp_message,
                    host=endpoint.host,
                    port=endpoint.port,
                    user=endpoint.user,
                    password=endpoint.password,
                    use_tls=endpoint.use_tls,
                    from_address=endpoint.from_address,
                    to=to,
                    subject=subject,
                    html=html,
                    text=text,
                    timeout=self.timeout,
                )
                if index > 0:
                    logger.info("SMTP delivered via fallback (%s)", endpoint.host)
                return EmailDeliveryResult(ok=True, provider=endpoint.label, message_id=message_id)
            except Exception as exc:
                last_code, last_summary = _format_smtp_error(exc)
                if index < len(endpoints) - 1:
                    logger.warning(
                        "SMTP primary failed (%s on %s:%s), trying fallback %s",
                        last_code,
                        endpoint.host,
                        endpoint.port,
                        endpoints[index + 1].host,
                    )
                    continue
                logger.warning("SMTP email failed: %s", last_code)

        return EmailDeliveryResult(
            ok=False,
            provider=endpoints[-1].label,
            error_code=last_code,
            error_summary=last_summary,
        )
