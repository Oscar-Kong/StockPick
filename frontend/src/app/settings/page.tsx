"use client";

import { PageContainer } from "@/components/ui/PageContainer";
import { PageHeader } from "@/components/ui/PageHeader";
import { ApiSettingsPanel } from "@/components/ApiSettingsPanel";
import { LanguageSettingsPanel } from "@/components/LanguageSettingsPanel";
import { QuantHealthCard } from "@/components/quant/QuantHealthCard";
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
    <PageContainer className="flex flex-1 flex-col gap-5 pb-8">
      <PageHeader
        title={t.settings.pageTitle}
        subtitle={t.settings.pageSubtitle}
        actions={
          <GhostButton onClick={close} className="rounded-lg text-sm">
            {t.settings.close}
          </GhostButton>
        }
      />

      <div className="settings-layout">
        <nav className="settings-nav" aria-label={t.settings.pageTitle}>
          <a href="#settings-language" className="settings-nav__link settings-nav__link--active">
            {t.settings.languageSection}
          </a>
          <a href="#settings-quant" className="settings-nav__link">
            {t.settings.quantHealthSection}
          </a>
          <a href="#settings-api" className="settings-nav__link">
            {t.settings.apiSection}
          </a>
        </nav>

        <div className="min-w-0 space-y-6">
          <section id="settings-language" className="settings-section">
            <LanguageSettingsPanel />
          </section>

          <section id="settings-quant" className="settings-section">
            <h2 className="settings-section__title">{t.settings.quantHealthSection}</h2>
            <QuantHealthCard />
          </section>

          <section id="settings-api" className="settings-section">
            <h2 className="settings-section__title">{t.settings.apiSection}</h2>
            <ApiSettingsPanel />
          </section>
        </div>
      </div>
    </PageContainer>
  );
}
