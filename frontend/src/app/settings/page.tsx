"use client";

import { PageHeader } from "@/components/ui/PageHeader";
import { ApiSettingsPanel } from "@/components/ApiSettingsPanel";
import { LanguageSettingsPanel } from "@/components/LanguageSettingsPanel";
import { QuantHealthCard } from "@/components/quant/QuantHealthCard";
import { CollapsibleSection } from "@/components/ui/CollapsibleSection";
import { GhostButton } from "@/components/ui/buttons";
import { useTranslation } from "@/lib/i18n";
import { useRouter } from "next/navigation";
import { useCallback, useEffect } from "react";

export default function SettingsPage() {
  const router = useRouter();
  const { t } = useTranslation();

  const close = useCallback(() => {
    if (typeof window !== "undefined" && window.history.length > 1) {
      router.back();
    } else {
      router.push("/");
    }
  }, [router]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [close]);

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-6 pb-8">
      <PageHeader
        title={t.settings.pageTitle}
        subtitle={t.settings.pageSubtitle}
        actions={
          <GhostButton onClick={close} className="rounded-lg text-sm">
            {t.settings.close}
          </GhostButton>
        }
      />
      <LanguageSettingsPanel />
      <CollapsibleSection title={t.settings.quantHealthSection} defaultOpen>
        <QuantHealthCard />
      </CollapsibleSection>
      <section>
        <h2 className="mb-3 text-sm font-semibold text-zinc-100">{t.settings.apiSection}</h2>
        <ApiSettingsPanel />
      </section>
    </div>
  );
}
