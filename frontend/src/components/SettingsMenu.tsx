"use client";

import { useLocale, type Locale } from "@/lib/i18n";
import clsx from "clsx";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

export function SettingsMenu() {
  const { locale, setLocale, t } = useLocale();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    window.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      window.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const pick = (next: Locale) => {
    setLocale(next);
    setOpen(false);
  };

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="settings-nav-btn flex items-center gap-1 rounded-lg px-2 py-2 text-zinc-500 transition hover:bg-zinc-900 hover:text-zinc-200"
        title={t.settings.menuTitle}
        aria-label={t.settings.menuTitle}
        aria-expanded={open}
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden>
          <path
            d="M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z"
            stroke="currentColor"
            strokeWidth="1.75"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <path
            d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1Z"
            stroke="currentColor"
            strokeWidth="1.75"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
        <span className="hidden text-xs font-medium uppercase tracking-wide sm:inline">
          {locale === "zh" ? "中" : "EN"}
        </span>
      </button>

      {open && (
        <div className="absolute right-0 top-full z-50 mt-1 w-56 rounded-lg border border-zinc-700 bg-zinc-950 py-1 shadow-xl">
          <p className="px-3 py-2 text-xs font-medium uppercase tracking-wide text-zinc-500">
            {t.settings.language}
          </p>
          <div className="flex gap-1 px-2 pb-2">
            {(
              [
                ["en", t.settings.english],
                ["zh", t.settings.chinese],
              ] as const
            ).map(([code, label]) => (
              <button
                key={code}
                type="button"
                onClick={() => pick(code)}
                className={clsx(
                  "flex-1 rounded-md px-2 py-1.5 text-xs font-medium transition",
                  locale === code
                    ? "bg-primary/20 text-primary ring-1 ring-primary/40"
                    : "text-zinc-400 hover:bg-zinc-900 hover:text-zinc-200"
                )}
              >
                {label}
              </button>
            ))}
          </div>
          <div className="my-1 border-t border-zinc-800" />
          <Link
            href="/settings"
            onClick={() => setOpen(false)}
            className="flex flex-col px-3 py-2 text-sm text-zinc-300 transition hover:bg-zinc-900"
          >
            <span>{t.settings.apiSettings}</span>
            <span className="text-xs text-zinc-500">{t.settings.apiSettingsDesc}</span>
          </Link>
        </div>
      )}
    </div>
  );
}
