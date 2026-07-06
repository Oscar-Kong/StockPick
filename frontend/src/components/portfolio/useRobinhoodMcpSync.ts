"use client";

import { useCallback, useState } from "react";
import { syncRobinhoodMcp } from "@/lib/api/portfolio";
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
      const result = await syncRobinhoodMcp();
      const positions = result.holdings_count ?? result.holdings?.length ?? 0;
      const orders = result.orders_imported ?? 0;
      const parts = [t.portfolio.robinhoodLiveSyncDone];
      if (positions > 0) parts.push(`(${positions} positions)`);
      if (orders > 0) {
        parts.push(fmt(t.portfolio.robinhoodLiveSyncDoneOrders, { orders }));
      }
      setMessage(parts.join(" · "));
      onComplete();
    } catch (err) {
      setError(err instanceof Error ? err.message : t.portfolio.robinhoodLiveSyncFailed);
    } finally {
      setSyncing(false);
    }
  }, [onComplete, t.portfolio.robinhoodLiveSyncDone, t.portfolio.robinhoodLiveSyncDoneOrders, t.portfolio.robinhoodLiveSyncFailed]);

  return { syncing, message, error, sync, setError, setMessage };
}
