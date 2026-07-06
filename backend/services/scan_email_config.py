"""Morning scan email configuration and validation."""
from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field

from buckets import ACTIVE_BUCKETS

logger = logging.getLogger(__name__)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_FROM_RE = re.compile(r"^(?:(.+?)\s*)?<([^>]+)>$|^(?P<plain>[^@\s]+@[^@\s]+\.[^@\s]+)$")


@dataclass(frozen=True)
class ScanEmailSettings:
    enabled: bool
    provider: str
    recipients: tuple[str, ...]
    from_address: str
    buckets: tuple[str, ...]
    top_n: int
    cron: str
    timezone: str
    stale_after_minutes: int
    retry_delay_minutes: int
    max_retries: int
    public_url: str
    config_valid: bool
    config_errors: tuple[str, ...] = field(default_factory=tuple)

    @property
    def recipient_hash(self) -> str:
        return hash_recipients(self.recipients)


def parse_recipients(raw: str) -> list[str]:
    return _parse_recipients(raw)


def _parse_recipients(raw: str) -> list[str]:
    parts = [p.strip() for p in (raw or "").split(",") if p.strip()]
    return parts


def _parse_buckets(raw: str) -> list[str]:
    parts = [p.strip().lower() for p in (raw or "").split(",") if p.strip()]
    allowed = set(ACTIVE_BUCKETS)
    return [b for b in parts if b in allowed]


def _validate_from_address(value: str) -> bool:
    if not value:
        return False
    match = _FROM_RE.match(value.strip())
    if not match:
        return False
    email = match.group(2) or match.group("plain")
    return bool(email and _EMAIL_RE.match(email))


def load_scan_email_settings() -> ScanEmailSettings:
    from config import (
        APP_PUBLIC_URL,
        SCAN_EMAIL_BUCKETS_RAW,
        SCAN_EMAIL_CRON,
        SCAN_EMAIL_ENABLED,
        SCAN_EMAIL_FROM,
        SCAN_EMAIL_MAX_RETRIES,
        SCAN_EMAIL_PROVIDER,
        SCAN_EMAIL_RETRY_DELAY_MINUTES,
        SCAN_EMAIL_STALE_AFTER_MINUTES,
        SCAN_EMAIL_TIMEZONE,
        SCAN_EMAIL_TOP_N,
        SMTP_PASSWORD,
        SMTP_USER,
    )
    from services.mailing_list_store import resolve_scan_email_recipients

    recipients_raw, _source = resolve_scan_email_recipients()
    recipients = list(recipients_raw)
    buckets = _parse_buckets(SCAN_EMAIL_BUCKETS_RAW) or tuple(ACTIVE_BUCKETS)
    errors: list[str] = []

    if SCAN_EMAIL_ENABLED:
        if not recipients:
            errors.append(
                "At least one recipient is required when SCAN_EMAIL_ENABLED=true "
                "(add emails in Settings → Ops → Mailing list, or set SCAN_EMAIL_TO in .env)"
            )
        else:
            for addr in recipients:
                if not _EMAIL_RE.match(addr):
                    errors.append(f"Invalid recipient address: {mask_email(addr)}")
        if not _validate_from_address(SCAN_EMAIL_FROM):
            errors.append("SCAN_EMAIL_FROM must be a valid email or 'Name <email@domain>'")
        if not buckets:
            errors.append("SCAN_EMAIL_BUCKETS must include at least one active bucket")
        provider = (SCAN_EMAIL_PROVIDER or "smtp").lower()
        if provider == "smtp":
            if not SMTP_USER:
                errors.append("SMTP_USER is required when SCAN_EMAIL_PROVIDER=smtp")
            if not SMTP_PASSWORD:
                errors.append("SMTP_PASSWORD is required when SCAN_EMAIL_PROVIDER=smtp (use a Gmail App Password)")

    config_valid = not errors
    if SCAN_EMAIL_ENABLED and errors:
        logger.warning(
            "Morning scan email disabled due to configuration errors: %s",
            "; ".join(errors),
        )

    return ScanEmailSettings(
        enabled=bool(SCAN_EMAIL_ENABLED) and config_valid,
        provider=(SCAN_EMAIL_PROVIDER or "smtp").lower(),
        recipients=tuple(recipients),
        from_address=SCAN_EMAIL_FROM.strip(),
        buckets=tuple(buckets),
        top_n=max(1, int(SCAN_EMAIL_TOP_N)),
        cron=SCAN_EMAIL_CRON,
        timezone=SCAN_EMAIL_TIMEZONE,
        stale_after_minutes=max(1, int(SCAN_EMAIL_STALE_AFTER_MINUTES)),
        retry_delay_minutes=max(1, int(SCAN_EMAIL_RETRY_DELAY_MINUTES)),
        max_retries=max(0, int(SCAN_EMAIL_MAX_RETRIES)),
        public_url=APP_PUBLIC_URL.rstrip("/"),
        config_valid=config_valid,
        config_errors=tuple(errors),
    )


def hash_recipients(recipients: tuple[str, ...] | list[str]) -> str:
    normalized = ",".join(sorted({r.strip().lower() for r in recipients if r.strip()}))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:32]


def mask_email(email: str) -> str:
    email = (email or "").strip()
    if not email or "@" not in email:
        return "***"
    local, domain = email.split("@", 1)
    if len(local) <= 1:
        masked_local = f"{local}***" if local else "*"
    else:
        masked_local = f"{local[0]}***"
    return f"{masked_local}@{domain}"


def mask_recipients(recipients: tuple[str, ...] | list[str]) -> str:
    if not recipients:
        return "—"
    masked = [mask_email(r) for r in recipients]
    if len(masked) == 1:
        return masked[0]
    return f"{masked[0]} (+{len(masked) - 1} more)"


def extract_email_address(value: str) -> str:
    """Return bare email from 'Name <email@domain>' or plain address."""
    value = (value or "").strip()
    if not value:
        return ""
    match = _FROM_RE.match(value)
    if match:
        email = match.group(2) or match.group("plain")
        return (email or "").strip()
    return value


def format_recipient_list(recipients: tuple[str, ...] | list[str]) -> str:
    cleaned = [r.strip() for r in recipients if r and r.strip()]
    if not cleaned:
        return "—"
    if len(cleaned) == 1:
        return cleaned[0]
    return ", ".join(cleaned)
