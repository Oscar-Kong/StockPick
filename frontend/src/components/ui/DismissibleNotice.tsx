"use client";

import clsx from "clsx";
import type { ReactNode } from "react";
import { useCallback, useSyncExternalStore } from "react";
import {
  dismissNotice,
  EMPTY_DISMISSED_NOTICES,
  getDismissedNoticesSnapshot,
  notifyDismissedNoticesChanged,
  subscribeDismissedNotices,
} from "@/lib/dismissedNotices";
import { useTranslation } from "@/lib/i18n";

interface DismissibleNoticeProps {
  noticeId: string;
  className?: string;
  role?: "status" | "alert";
  children: ReactNode;
}

export function DismissibleNotice({ noticeId, className, role = "status", children }: DismissibleNoticeProps) {
  const { t } = useTranslation();
  const dismissed = useSyncExternalStore(
    subscribeDismissedNotices,
    getDismissedNoticesSnapshot,
    () => EMPTY_DISMISSED_NOTICES
  );
  const isDismissed = dismissed.has(noticeId);

  const onDismiss = useCallback(() => {
    dismissNotice(noticeId);
    notifyDismissedNoticesChanged();
  }, [noticeId]);

  if (isDismissed) return null;

  return (
    <div className={clsx("relative", className)} role={role}>
      <div className="pr-8">{children}</div>
      <button
        type="button"
        onClick={onDismiss}
        aria-label={t.common.close}
        className="absolute right-2 top-2 flex h-7 w-7 items-center justify-center rounded-md text-zinc-400 transition hover:bg-white/8 hover:text-zinc-100"
      >
        <span aria-hidden className="text-lg leading-none">
          ×
        </span>
      </button>
    </div>
  );
}
