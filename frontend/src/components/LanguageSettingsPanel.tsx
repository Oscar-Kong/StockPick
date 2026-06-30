"use client";

import { useLocale, type Locale } from "@/lib/i18n";
import clsx from "clsx";

export function LanguageSettingsPanel() {
  const { locale, setLocale, t } = useLocale();

  return (
    <section className="surface-card mb-6 p-4 sm:p-5">
      <h2 className="text-sm font-semibold text-foreground">{t.settings.languageSection}</h2>
      <p className="mt-1 text-xs text-secondary">{t.settings.languageHint}</p>
      <div className="mt-3 flex gap-2">
        {(
          [
            ["en", t.settings.english],
            ["zh", t.settings.chinese],
          ] as const
        ).map(([code, label]) => (
          <button
            key={code}
            type="button"
            onClick={() => setLocale(code as Locale)}
            className={clsx(
              "rounded-lg px-4 py-2 text-sm font-medium transition",
              locale === code
                ? "bg-primary/15 text-primary ring-1 ring-primary/40"
                : "border border-[var(--border-subtle)] text-secondary hover:border-[var(--border-strong)] hover:text-foreground"
            )}
          >
            {label}
          </button>
        ))}
      </div>
    </section>
  );
}
