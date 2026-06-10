"""Optional SnapTrade read-only sync (no credentials stored in app DB)."""
from __future__ import annotations

import logging
import os

from integrations.robinhood.base import BrokerageProvider
from integrations.robinhood.models import BrokerageSyncResult

logger = logging.getLogger(__name__)


class SnapTradeClient(BrokerageProvider):
    source = "snaptrade"

    def is_configured(self) -> bool:
        return bool(
            os.getenv("SNAPTRADE_CLIENT_ID", "").strip()
            and os.getenv("SNAPTRADE_CONSUMER_SECRET", "").strip()
        )

    def sync_holdings(self) -> BrokerageSyncResult:
        if not self.is_configured():
            return BrokerageSyncResult(
                source="snaptrade",
                message="SnapTrade not configured — set SNAPTRADE_CLIENT_ID and SNAPTRADE_CONSUMER_SECRET",
            )
        # Read-only placeholder: full OAuth flow belongs in a separate auth UI session.
        logger.info("SnapTrade configured but sync not implemented — use CSV import")
        return BrokerageSyncResult(
            source="snaptrade",
            message="SnapTrade credentials detected. Connect via SnapTrade portal; CSV import available meanwhile.",
        )
