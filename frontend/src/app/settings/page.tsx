"use client";

import { PageContainer } from "@/components/ui/PageContainer";
import { PageHeader } from "@/components/ui/PageHeader";
import { ApiSettingsPanel } from "@/components/ApiSettingsPanel";
import { QuantHealthCard } from "@/components/quant/QuantHealthCard";
import { LanguageSettingsPanel } from "@/components/LanguageSettingsPanel";
import { MorningScanEmailPanel } from "@/components/settings/MorningScanEmailPanel";
import { GhostButton } from "@/components/ui/buttons";
import { useTranslation } from "@/lib/i18n";
import clsx from "clsx";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect } from "react";

export type SettingsSection = "language" | "quant-health" | "api" | "ops";

const SECTIONS: SettingsSection[] = ["language", "quant-health", "api", "ops"];

function parseSection(value: string | null): SettingsSection {
  if (value === "quant-health" || value === "api" || value === "ops") return value;
  return "language";
}

function SettingsContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { t } = useTranslation();
  const section = parseSection(searchParams.get("section"));

  const setSection = useCallback(
    (next: SettingsSection) => {
      const params = new URLSearchParams(searchParams.toString());
      params.set("section", next);
      router.replace(`/settings?${params.toString()}`);
    },
    [router, searchParams]
  );

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

  const sectionLabels: Record<SettingsSection, string> = {
    language: t.settings.sectionLanguage,
    "quant-health": t.settings.sectionQuantHealth,
    api: t.settings.sectionApi,
    ops: t.settings.sectionOps,
  };

  return (
    <PageContainer className="settings-shell flex flex-1 flex-col gap-4 pb-8">
      <PageHeader
        title={t.settings.pageTitle}
        subtitle={t.settings.pageSubtitle}
        actions={
          <GhostButton onClick={close} className="rounded-lg text-sm">
            {t.settings.close}
          </GhostButton>
        }
      />

      <label className="settings-mobile-select md:hidden">
        <span className="sr-only">{t.settings.mobileSectionLabel}</span>
        <select
          className="input-field w-full text-sm"
          value={section}
          onChange={(e) => setSection(parseSection(e.target.value))}
        >
          {SECTIONS.map((id) => (
            <option key={id} value={id}>
              {sectionLabels[id]}
            </option>
          ))}
        </select>
      </label>

      <div className="settings-layout">
        <nav className="settings-nav hidden md:flex" aria-label={t.settings.pageTitle}>
          {SECTIONS.map((id) => (
            <button
              key={id}
              type="button"
              className={clsx("settings-nav__link", section === id && "settings-nav__link--active")}
              aria-current={section === id ? "page" : undefined}
              onClick={() => setSection(id)}
            >
              {sectionLabels[id]}
            </button>
          ))}
        </nav>

        <div className="settings-panel min-w-0">
          {section === "language" && (
            <section aria-labelledby="settings-language-title">
              <h2 id="settings-language-title" className="settings-section__title">
                {t.settings.languageSection}
              </h2>
              <p className="mb-4 text-sm text-secondary">{t.settings.languageHint}</p>
              <LanguageSettingsPanel />
            </section>
          )}

          {section === "quant-health" && (
            <section aria-labelledby="settings-quant-title">
              <h2 id="settings-quant-title" className="settings-section__title">
                {t.settings.quantHealthSection}
              </h2>
              <QuantHealthCard />
            </section>
          )}

          {section === "api" && (
            <section aria-labelledby="settings-api-title">
              <h2 id="settings-api-title" className="settings-section__title">
                {t.settings.apiSection}
              </h2>
              <ApiSettingsPanel />
            </section>
          )}

          {section === "ops" && (
            <section aria-labelledby="settings-ops-title">
              <h2 id="settings-ops-title" className="settings-section__title">
                {t.settings.sectionOps}
              </h2>
              <MorningScanEmailPanel />
            </section>
          )}
        </div>
      </div>
    </PageContainer>
  );
}

export default function SettingsPage() {
  const { t } = useTranslation();
  return (
    <Suspense fallback={<p className="text-sm text-secondary">{t.common.loading}</p>}>
      <SettingsContent />
    </Suspense>
  );
}
