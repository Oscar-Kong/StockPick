"use client";

import { TradingHistoryModule } from "@/components/portfolio/TradingHistoryModule";

export type PortfolioActivityProps = {
  reloadToken?: number;
  onSyncRobinhood?: () => void;
  syncingRobinhood?: boolean;
  syncDisabled?: boolean;
  syncMessage?: string | null;
  syncError?: string | null;
};

export function PortfolioActivity({
  reloadToken,
  onSyncRobinhood,
  syncingRobinhood,
  syncDisabled,
  syncMessage,
  syncError,
}: PortfolioActivityProps) {
  return (
    <TradingHistoryModule
      reloadToken={reloadToken}
      onSync={onSyncRobinhood}
      syncing={syncingRobinhood}
      syncDisabled={syncDisabled}
      syncMessage={syncMessage}
      syncError={syncError}
    />
  );
}
