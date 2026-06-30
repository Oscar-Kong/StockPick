"use client";

import { openCommandPalette } from "@/components/CommandPalette";
import { useLocale, useTranslation } from "@/lib/i18n";
import clsx from "clsx";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";

type PrimaryItem = {
  href: string;
  label: string;
  match?: readonly string[];
  icon: React.ReactNode;
};

function NavIcon({ children }: { children: React.ReactNode }) {
  return (
    <span className="mobile-bottom-nav__icon" aria-hidden>
      {children}
    </span>
  );
}

function isActive(pathname: string, href: string, match?: readonly string[]) {
  if (pathname === href) return true;
  const prefixes = match ?? [href];
  return prefixes.some((p) => pathname === p || pathname.startsWith(p + "/"));
}

export function MobileBottomNav() {
  const pathname = usePathname();
  const { t } = useTranslation();
  const { locale, setLocale } = useLocale();
  const [moreOpen, setMoreOpen] = useState(false);
  const moreRef = useRef<HTMLDivElement>(null);

  const primary: PrimaryItem[] = [
    {
      href: "/",
      label: t.nav.portfolio,
      icon: (
        <NavIcon>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
            <path
              d="M4 10.5 12 4l8 6.5V20a1 1 0 0 1-1 1h-5v-6H10v6H5a1 1 0 0 1-1-1v-9.5Z"
              stroke="currentColor"
              strokeWidth="1.75"
              strokeLinejoin="round"
            />
          </svg>
        </NavIcon>
      ),
    },
    {
      href: "/scan",
      label: t.nav.scan,
      match: ["/scan", "/penny", "/medium", "/compounder"],
      icon: (
        <NavIcon>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
            <circle cx="11" cy="11" r="6.5" stroke="currentColor" strokeWidth="1.75" />
            <path d="m16.5 16.5 4 4" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" />
          </svg>
        </NavIcon>
      ),
    },
    {
      href: "/workspace",
      label: t.nav.analyze,
      match: ["/workspace", "/watchlist", "/analyze", "/trades"],
      icon: (
        <NavIcon>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
            <path d="M4 19V5" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" />
            <path
              d="M4 15h4l2-5 3 10 2-6h5"
              stroke="currentColor"
              strokeWidth="1.75"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </NavIcon>
      ),
    },
    {
      href: "/quant-lab",
      label: t.nav.quantLab,
      match: ["/quant-lab"],
      icon: (
        <NavIcon>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
            <path
              d="M10 3h4l1 5-3 2-3-2 1-5ZM6 14l3 7 3-4 3 4 3-7"
              stroke="currentColor"
              strokeWidth="1.75"
              strokeLinejoin="round"
            />
          </svg>
        </NavIcon>
      ),
    },
  ];

  const moreActive =
    isActive(pathname, "/library", ["/library", "/scans", "/reports"]) ||
    isActive(pathname, "/settings", ["/settings"]) ||
    isActive(pathname, "/trader-intel", ["/trader-intel"]);

  useEffect(() => {
    if (!moreOpen) return;
    const onDoc = (e: MouseEvent) => {
      if (moreRef.current && !moreRef.current.contains(e.target as Node)) setMoreOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setMoreOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    window.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      window.removeEventListener("keydown", onKey);
    };
  }, [moreOpen]);

  return (
    <nav className="mobile-bottom-nav" aria-label={t.navAria.mobile}>
      <div className="mobile-bottom-nav__inner">
        {primary.map((item) => {
          const active = isActive(pathname, item.href, item.match);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={clsx("mobile-bottom-nav__link", active && "mobile-bottom-nav__link--active")}
              aria-current={active ? "page" : undefined}
            >
              {item.icon}
              <span className="mobile-bottom-nav__label">{item.label}</span>
            </Link>
          );
        })}

        <div ref={moreRef} className="mobile-bottom-nav__more">
          <button
            type="button"
            className={clsx(
              "mobile-bottom-nav__link mobile-bottom-nav__more-btn",
              (moreOpen || moreActive) && "mobile-bottom-nav__link--active"
            )}
            aria-expanded={moreOpen}
            aria-haspopup="true"
            aria-label={t.nav.more}
            onClick={() => setMoreOpen((v) => !v)}
          >
            <NavIcon>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
                <circle cx="6" cy="12" r="1.5" fill="currentColor" />
                <circle cx="12" cy="12" r="1.5" fill="currentColor" />
                <circle cx="18" cy="12" r="1.5" fill="currentColor" />
              </svg>
            </NavIcon>
            <span className="mobile-bottom-nav__label">{t.nav.more}</span>
          </button>

          {moreOpen && (
            <div className="mobile-bottom-nav__menu" role="menu">
              <Link
                href="/library"
                role="menuitem"
                className="mobile-bottom-nav__menu-item"
                onClick={() => setMoreOpen(false)}
              >
                {t.nav.library}
              </Link>
              <Link
                href="/trader-intel"
                role="menuitem"
                className="mobile-bottom-nav__menu-item"
                onClick={() => setMoreOpen(false)}
              >
                {t.nav.traderIntel}
              </Link>
              <Link
                href="/settings"
                role="menuitem"
                className="mobile-bottom-nav__menu-item"
                onClick={() => setMoreOpen(false)}
              >
                {t.nav.settings}
              </Link>
              <div className="mobile-bottom-nav__menu-divider" role="separator" />
              <p className="mobile-bottom-nav__menu-heading">{t.nav.theme}</p>
              <span className="mobile-bottom-nav__menu-meta">{t.nav.themeDark}</span>
              <div className="mobile-bottom-nav__menu-divider" role="separator" />
              <p className="mobile-bottom-nav__menu-heading">{t.settings.language}</p>
              <div className="mobile-bottom-nav__lang-row">
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
                    className={clsx(
                      "mobile-bottom-nav__lang-btn",
                      locale === code && "mobile-bottom-nav__lang-btn--active"
                    )}
                    aria-checked={locale === code}
                    onClick={() => {
                      setLocale(code);
                      setMoreOpen(false);
                    }}
                  >
                    {label}
                  </button>
                ))}
              </div>
              <div className="mobile-bottom-nav__menu-divider" role="separator" />
              <button
                type="button"
                role="menuitem"
                className="mobile-bottom-nav__menu-item"
                onClick={() => {
                  setMoreOpen(false);
                  openCommandPalette();
                }}
              >
                {t.command.search}
              </button>
            </div>
          )}
        </div>
      </div>
    </nav>
  );
}
