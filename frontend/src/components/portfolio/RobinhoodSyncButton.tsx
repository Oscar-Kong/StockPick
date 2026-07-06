"use client";

import { GhostButton } from "@/components/ui/buttons";
import { useTranslation } from "@/lib/i18n";

type RobinhoodSyncButtonProps = {
  syncing: boolean;
  disabled?: boolean;
  onSync: () => void;
};

/** Compact Robinhood MCP sync — for Today tab header actions. */
export function RobinhoodSyncButton({ syncing, disabled, onSync }: RobinhoodSyncButtonProps) {
  const { t } = useTranslation();
  return (
    <GhostButton size="sm" onClick={onSync} disabled={disabled || syncing} title={t.portfolio.robinhoodLiveSubtitle}>
      {syncing ? t.portfolio.robinhoodLiveSyncingShort : t.portfolio.robinhoodLiveSyncShort}
    </GhostButton>
  );
}
