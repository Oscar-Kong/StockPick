"use client";

import { DismissibleNotice } from "@/components/ui/DismissibleNotice";
import { getHealth } from "@/lib/api";
import { useTranslation } from "@/lib/i18n";
import { useEffect, useState } from "react";

const NOTICE_ID = "public-demo-environment";

export function PublicDemoBanner() {
  const { t } = useTranslation();
  const [demoMode, setDemoMode] = useState<boolean | null>(null);

  useEffect(() => {
    getHealth()
      .then((h) => setDemoMode(Boolean(h.demo_mode)))
      .catch(() => setDemoMode(false));
  }, []);

  if (!demoMode) return null;

  return (
    <DismissibleNotice
      noticeId={NOTICE_ID}
      role="status"
      className="border-b border-amber-500/25 bg-amber-500/8 px-4 py-2"
    >
      <div className="mx-auto flex max-w-[1920px] flex-wrap items-center gap-2 text-sm text-amber-100/95">
        <span className="rounded-full border border-amber-400/40 bg-amber-500/15 px-2 py-0.5 text-xs font-semibold text-amber-200">
          {t.demo.publicPill}
        </span>
        <span>{t.demo.publicBanner}</span>
      </div>
    </DismissibleNotice>
  );
}
