"""No-op email provider for tests and dry-run validation."""
from __future__ import annotations

import logging

from services.email.types import EmailDeliveryResult

logger = logging.getLogger(__name__)


class NoopEmailProvider:
    async def send_email(
        self,
        *,
        to: list[str],
        subject: str,
        html: str,
        text: str,
        from_address: str,
    ) -> EmailDeliveryResult:
        logger.info(
            "Noop email provider — subject=%r html_len=%s text_len=%s",
            subject[:80],
            len(html),
            len(text),
        )
        return EmailDeliveryResult(ok=True, provider="noop", message_id="noop-local")
