"use client";

import clsx from "clsx";
import { useTranslation } from "@/lib/i18n";
import { AppTabBar, AppTabButton } from "@/components/AppTabs";

export interface DetailDrawerTab {
  id: string;
  label: string;
}

interface DetailDrawerProps {
  open: boolean;
  title: string;
  subtitle?: string;
  tabs?: DetailDrawerTab[];
  activeTab?: string;
  onTabChange?: (tabId: string) => void;
  onClose: () => void;
  loading?: boolean;
  children: React.ReactNode;
  className?: string;
}

export function DetailDrawer({
  open,
  title,
  subtitle,
  tabs,
  activeTab,
  onTabChange,
  onClose,
  loading,
  children,
  className,
}: DetailDrawerProps) {
  const { t } = useTranslation();
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/40">
      <div
        className={clsx(
          "detail-drawer-panel flex h-full w-full flex-col bg-zinc-950 shadow-xl",
          className
        )}
      >
        <div className="flex items-start justify-between gap-3 border-b border-zinc-200 px-5 py-4 dark:border-zinc-800">
          <div className="min-w-0">
            <h2 className="truncate text-lg font-semibold text-zinc-50">{title}</h2>
            {subtitle && <p className="text-sm text-secondary">{subtitle}</p>}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="shrink-0 rounded-lg px-3 py-1.5 text-sm hover:bg-zinc-900"
          >
            {t.common.close}
          </button>
        </div>

        {tabs && tabs.length > 0 && activeTab && onTabChange && (
          <div className="border-b border-zinc-200 px-3 dark:border-zinc-800">
            <AppTabBar className="overflow-x-auto">
              {tabs.map((tab) => (
                <AppTabButton
                  key={tab.id}
                  active={activeTab === tab.id}
                  onClick={() => onTabChange(tab.id)}
                >
                  {tab.label}
                </AppTabButton>
              ))}
            </AppTabBar>
          </div>
        )}

        <div className="relative flex-1 overflow-y-auto p-5">
          {loading && (
            <p className="absolute inset-x-5 top-4 text-sm text-secondary">{t.common.loading}</p>
          )}
          {children}
        </div>
      </div>
    </div>
  );
}
