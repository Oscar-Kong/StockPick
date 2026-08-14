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
      // Slim Sync: positions + buying power + KPIs + latest trade.
      // Daily decision is a separate deliberate click.
      const result = await syncRobinhoodMcp(false);
      const positions = result.holdings_count ?? result.holdings?.length ?? 0;
      const parts = [t.portfolio.robinhoodLiveSyncDone];
      if (positions === 0) {
        parts.push(t.portfolio.robinhoodLiveSyncCashOnly);
      } else {
        parts.push(`(${positions} positions)`);
      }
      if (typeof result.cash === "number") {
        parts.push(
          fmt(t.portfolio.robinhoodLiveSyncBuyingPower, {
            cash: result.cash.toLocaleString(undefined, {
              style: "currency",
              currency: "USD",
            }),
          }),
        );
      }
      const lt = result.latest_trade;
      if (lt?.symbol) {
        parts.push(
          fmt(t.portfolio.robinhoodLiveSyncLatestTrade, {
            side: String(lt.side || "").toUpperCase() || "TRADE",
            symbol: lt.symbol,
          }),
        );
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
    t.portfolio.robinhoodLiveSyncBuyingPower,
    t.portfolio.robinhoodLiveSyncCashOnly,
    t.portfolio.robinhoodLiveSyncDone,
    t.portfolio.robinhoodLiveSyncFailed,
    t.portfolio.robinhoodLiveSyncLatestTrade,
  ]);

  return { syncing, message, error, sync, setError, setMessage };
}
