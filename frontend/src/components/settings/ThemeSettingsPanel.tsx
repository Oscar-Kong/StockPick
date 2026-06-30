"use client";

import { useTheme } from "@/components/ThemeProvider";
import { useTranslation } from "@/lib/i18n";
import type { ThemePreference } from "@/lib/theme";
import clsx from "clsx";

const OPTIONS: ThemePreference[] = ["dark", "light", "system"];

export function ThemeSettingsPanel() {
  const { t } = useTranslation();
  const { preference, setPreference } = useTheme();

  const labels: Record<ThemePreference, string> = {
    dark: t.settings.themeDark,
    light: t.settings.themeLight,
    system: t.settings.themeSystem,
  };

  return (
    <div className="space-y-3" role="radiogroup" aria-label={t.settings.themeSection}>
      <div className="flex flex-wrap gap-2">
        {OPTIONS.map((option) => (
          <button
            key={option}
            type="button"
            role="radio"
            aria-checked={preference === option}
            onClick={() => setPreference(option)}
            className={clsx(
              "rounded-lg px-4 py-2 text-sm font-medium transition",
              preference === option
                ? "bg-primary/15 text-primary ring-1 ring-primary/40"
                : "border border-zinc-700 text-zinc-400 hover:border-zinc-500 hover:text-zinc-200"
            )}
          >
            {labels[option]}
          </button>
        ))}
      </div>
      <p className="text-sm text-secondary">{t.settings.themeHint}</p>
    </div>
  );
}
