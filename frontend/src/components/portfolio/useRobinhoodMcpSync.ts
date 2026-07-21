"use client";

import { useCallback, useState } from "react";
import { RobinhoodMcpSyncTimeoutError, syncRobinhoodMcp } from "@/lib/api/portfolio";
import { useTranslation, fmt } from "@/lib/i18n";

export function useRobinhoodMcpSync(onComplete: () => void) {
  const { t } = useTranslation();
  const [syncing, setSyncing] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const sync = useCallback(async () => {
    setSyncing(true);
    setError(null);
    setMessage(null);
    try {
      // Re-run daily decision so Today marks/shares match live holdings
      // (sync alone used to leave a stale decision snapshot on screen).
      // Backend skips decision when holdings_count is 0 (cash-only).
      const result = await syncRobinhoodMcp(true);
      const positions = result.holdings_count ?? result.holdings?.length ?? 0;
      const orders = result.orders_imported ?? 0;
      const parts = [t.portfolio.robinhoodLiveSyncDone];
      if (positions === 0) {
        parts.push(t.portfolio.robinhoodLiveSyncCashOnly);
      } else {
        parts.push(`(${positions} positions)`);
      }
      if (orders > 0) {
        parts.push(fmt(t.portfolio.robinhoodLiveSyncDoneOrders, { orders }));
      }
      setMessage(parts.join(" · "));
      onComplete();
    } catch (err) {
      // Soft timeout: MCP is fine; job may still complete — refresh + info tone, not red failure.
      if (err instanceof RobinhoodMcpSyncTimeoutError) {
        setMessage(err.message);
        onComplete();
      } else {
        setError(err instanceof Error ? err.message : t.portfolio.robinhoodLiveSyncFailed);
      }
    } finally {
      setSyncing(false);
    }
  }, [
    onComplete,
    t.portfolio.robinhoodLiveSyncCashOnly,
    t.portfolio.robinhoodLiveSyncDone,
    t.portfolio.robinhoodLiveSyncDoneOrders,
    t.portfolio.robinhoodLiveSyncFailed,
  ]);

  return { syncing, message, error, sync, setError, setMessage };
}
