"use client";

import { useLocale, type Locale } from "@/lib/i18n";
import clsx from "clsx";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

function SettingsIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden className="settings-nav-btn__icon">
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
  );
}

const QUICK_LINKS = [
  { section: "theme", labelKey: "sectionTheme" as const },
  { section: "api", labelKey: "sectionApi" as const },
  { section: "quant-health", labelKey: "sectionQuantHealth" as const },
] as const;

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
        className="settings-nav-btn"
        title={t.settings.menuTitle}
        aria-label={t.settings.menuTitle}
        aria-expanded={open}
        aria-haspopup="menu"
      >
        <SettingsIcon />
        <span className="settings-nav-btn__label">{t.nav.settings}</span>
      </button>

      {open && (
        <div className="settings-menu-dropdown" role="menu" aria-label={t.settings.menuTitle}>
          <Link
            href="/settings"
            role="menuitem"
            onClick={() => setOpen(false)}
            className="settings-menu-dropdown__hero"
          >
            <span className="settings-menu-dropdown__hero-title">{t.settings.menuAllSettings}</span>
            <span className="settings-menu-dropdown__hero-desc">{t.settings.pageSubtitle}</span>
          </Link>

          <div className="settings-menu-dropdown__divider" role="separator" />

          <p className="settings-menu-dropdown__heading">{t.settings.language}</p>
          <div className="settings-menu-dropdown__lang-row">
            {(
              [
                ["en", t.settings.english],
                ["zh", t.settings.chinese],
              ] as const
            ).map(([code, label]) => (
              <button
                key={code}
                type="button"
                role="menuitemradio"
                aria-checked={locale === code}
                onClick={() => pick(code)}
                className={clsx(
                  "settings-menu-dropdown__lang-btn",
                  locale === code && "settings-menu-dropdown__lang-btn--active"
                )}
              >
                {label}
              </button>
            ))}
          </div>

          <div className="settings-menu-dropdown__divider" role="separator" />

          <p className="settings-menu-dropdown__heading">{t.settings.menuQuickLinks}</p>
          {QUICK_LINKS.map(({ section, labelKey }) => (
            <Link
              key={section}
              href={`/settings?section=${section}`}
              role="menuitem"
              onClick={() => setOpen(false)}
              className="settings-menu-dropdown__link"
            >
              {t.settings[labelKey]}
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
