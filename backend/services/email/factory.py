"""Email provider factory."""
from __future__ import annotations

from config import DEMO_MODE, SCAN_EMAIL_PROVIDER
from services.email.noop_provider import NoopEmailProvider
from services.email.smtp_provider import SmtpEmailProvider
from services.email.types import EmailProvider


def get_email_provider(*, dry_run: bool = False) -> EmailProvider:
    if dry_run or DEMO_MODE:
        return NoopEmailProvider()
    provider = (SCAN_EMAIL_PROVIDER or "smtp").lower()
    if provider in ("noop", "fake", "none"):
        return NoopEmailProvider()
    if provider == "smtp":
        return SmtpEmailProvider()
    # Unknown provider — fall back to SMTP with a warning in logs
    return SmtpEmailProvider()
