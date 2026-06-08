"use client";

import { ApiSettingsPanel } from "@/components/ApiSettingsPanel";
import { LanguageSettingsPanel } from "@/components/LanguageSettingsPanel";
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
    <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col px-4 py-6 sm:px-6 sm:py-8">
      <header className="mb-6 flex items-start justify-between gap-4 sm:mb-8">
        <div className="min-w-0 flex-1">
          <h1 className="text-2xl font-semibold tracking-tight text-zinc-50">{t.settings.pageTitle}</h1>
          <p className="mt-2 max-w-xl text-sm text-zinc-500">{t.settings.pageSubtitle}</p>
        </div>
        <button
          type="button"
          onClick={close}
          className="settings-close-btn shrink-0 rounded-lg border border-zinc-700 px-3 py-1.5 text-sm text-zinc-400 transition hover:border-zinc-500 hover:bg-zinc-900 hover:text-zinc-100"
        >
          {t.settings.close}
        </button>
      </header>
      <LanguageSettingsPanel />
      <h2 className="mb-3 text-sm font-semibold text-zinc-300">{t.settings.apiSection}</h2>
      <ApiSettingsPanel />
    </div>
  );
}
