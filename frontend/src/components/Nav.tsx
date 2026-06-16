// Top navigation — modern retail pro shell.
"use client";

import { AppTabBar, AppTabLink } from "@/components/AppTabs";
import { CommandPalette, CommandPaletteTrigger } from "@/components/CommandPalette";
import { SettingsMenu } from "@/components/SettingsMenu";
import { useTranslation } from "@/lib/i18n";
import Link from "next/link";
import { usePathname } from "next/navigation";

type NavLink = {
  href: string;
  label: string;
  match?: readonly string[];
};

function useNavLinks(): NavLink[] {
  const { t } = useTranslation();
  return [
    { href: "/", label: t.nav.home },
    {
      href: "/scan",
      label: t.nav.scan,
      match: ["/scan", "/penny", "/medium", "/compounder"],
    },
    {
      href: "/workspace",
      label: t.nav.workspace,
      match: ["/workspace", "/watchlist", "/analyze", "/trades"],
    },
    { href: "/portfolio", label: t.nav.portfolio },
    { href: "/quant-lab", label: t.nav.quantLab, match: ["/quant-lab"] },
    { href: "/library", label: t.nav.library, match: ["/library", "/scans", "/reports"] },
    { href: "/settings", label: t.nav.settings, match: ["/settings"] },
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
  const links = useNavLinks();

  return (
    <>
      <header className="app-nav sticky top-0 z-40">
        <div className="app-nav-inner">
          <Link href="/" className="app-brand" aria-label="Home">
            <span className="app-brand-mark" aria-hidden />
            <span className="app-brand-text">
              <span className="app-brand-name">Picker</span>
              <span className="app-brand-sub">Daily</span>
            </span>
          </Link>

          <div className="app-nav-center">
            <AppTabBar aria-label={t.navAria.main} className="app-nav-tabs">
              {links.map((link) => (
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
            <Link
              href="/trader-intel"
              className="hidden rounded-lg px-2.5 py-1.5 text-sm text-zinc-400 transition hover:bg-zinc-900 hover:text-zinc-200 md:inline"
            >
              {t.nav.traderIntel}
            </Link>
            <SettingsMenu />
            <CommandPaletteTrigger />
          </div>
        </div>
      </header>
      <CommandPalette />
    </>
  );
}
