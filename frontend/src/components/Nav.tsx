// Top navigation — modern retail pro shell.
"use client";

import { AppTabBar, AppTabLink } from "@/components/AppTabs";
import { CommandPalette, CommandPaletteTrigger } from "@/components/CommandPalette";
import { MobileBottomNav } from "@/components/MobileBottomNav";
import { SettingsMenu } from "@/components/SettingsMenu";
import { useTranslation } from "@/lib/i18n";
import clsx from "clsx";
import Link from "next/link";
import { usePathname } from "next/navigation";

type NavLink = {
  href: string;
  label: string;
  match?: readonly string[];
};

function usePrimaryNavLinks(): NavLink[] {
  const { t } = useTranslation();
  return [
    { href: "/", label: t.nav.portfolio },
    {
      href: "/scan",
      label: t.nav.scan,
      match: ["/scan", "/penny", "/medium", "/compounder"],
    },
    {
      href: "/workspace",
      label: t.nav.analyze,
      match: ["/workspace", "/watchlist", "/analyze", "/trades"],
    },
    { href: "/quant-lab", label: t.nav.quantLab, match: ["/quant-lab"] },
  ];
}

function useSecondaryNavLinks(): NavLink[] {
  const { t } = useTranslation();
  return [
    { href: "/library", label: t.nav.library, match: ["/library", "/scans", "/reports"] },
  ];
}

function isActive(pathname: string, href: string, match?: readonly string[]) {
  if (pathname === href) return true;
  const prefixes = match ?? [href];
  return prefixes.some((p) => pathname === p || pathname.startsWith(p + "/"));
}

export function Nav() {
  const pathname = usePathname();
  const { t } = useTranslation();
  const primaryLinks = usePrimaryNavLinks();
  const secondaryLinks = useSecondaryNavLinks();

  return (
    <>
      <header className="app-nav sticky top-0 z-40">
        <div className="app-nav-inner">
          <Link href="/" className="app-brand" aria-label="PickerQuant">
            <span className="app-brand-mark" aria-hidden />
            <span className="app-brand-text">
              <span className="app-brand-name">PickerQuant</span>
            </span>
          </Link>

          <div className="app-nav-center">
            <AppTabBar aria-label={t.navAria.main} className="app-nav-tabs">
              {primaryLinks.map((link) => (
                <AppTabLink
                  key={link.href}
                  href={link.href}
                  active={isActive(pathname, link.href, link.match)}
                >
                  {link.label}
                </AppTabLink>
              ))}
            </AppTabBar>
          </div>

          <div className="app-nav-actions">
            {secondaryLinks.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className={clsx(
                  "hidden rounded-lg px-2.5 py-1.5 text-sm transition md:inline",
                  isActive(pathname, link.href, link.match)
                    ? "bg-primary/10 text-primary"
                    : "text-zinc-400 hover:bg-zinc-900 hover:text-zinc-200"
                )}
                aria-current={isActive(pathname, link.href, link.match) ? "page" : undefined}
              >
                {link.label}
              </Link>
            ))}
            <Link
              href="/trader-intel"
              className={clsx(
                "hidden rounded-lg px-2.5 py-1.5 text-sm transition md:inline",
                isActive(pathname, "/trader-intel", ["/trader-intel"])
                  ? "bg-primary/10 text-primary"
                  : "text-zinc-400 hover:bg-zinc-900 hover:text-zinc-200"
              )}
              aria-current={isActive(pathname, "/trader-intel", ["/trader-intel"]) ? "page" : undefined}
            >
              {t.nav.traderIntel}
            </Link>
            <SettingsMenu />
            <CommandPaletteTrigger />
          </div>
        </div>
      </header>
      <CommandPalette />
      <MobileBottomNav />
    </>
  );
}
