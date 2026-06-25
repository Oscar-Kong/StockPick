"""Email delivery types and provider protocol."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class EmailDeliveryResult:
    ok: bool
    provider: str
    message_id: str | None = None
    error_code: str | None = None
    error_summary: str | None = None


class EmailProvider(Protocol):
    async def send_email(
        self,
        *,
        to: list[str],
        subject: str,
        html: str,
        text: str,
        from_address: str,
    ) -> EmailDeliveryResult:
        ...
