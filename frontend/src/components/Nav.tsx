// Top navigation — modern retail pro shell.
"use client";

import { AppTabBar, AppTabLink } from "@/components/AppTabs";
import { CommandPalette, CommandPaletteTrigger } from "@/components/CommandPalette";
import { SettingsMenu } from "@/components/SettingsMenu";
import { useTranslation } from "@/lib/i18n";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { Suspense } from "react";

type NavLink = {
  href: string;
  label: string;
  match?: readonly string[];
  workspaceTab?: "research" | "compare" | "journal";
};

function useNavLinks(): NavLink[] {
  const { t } = useTranslation();
  return [
    { href: "/", label: t.nav.home },
    {
      href: "/workspace",
      label: t.nav.research,
      match: ["/workspace", "/watchlist", "/analyze"],
      workspaceTab: "research",
    },
    {
      href: "/workspace?tab=compare",
      label: t.nav.compare,
      match: ["/workspace"],
      workspaceTab: "compare",
    },
    {
      href: "/workspace?tab=journal",
      label: t.nav.journal,
      match: ["/workspace", "/trades"],
      workspaceTab: "journal",
    },
    { href: "/scan", label: t.nav.screen, match: ["/scan", "/penny", "/medium", "/compounder"] },
    { href: "/portfolio", label: t.nav.portfolio },
    { href: "/library", label: t.nav.library, match: ["/library", "/scans", "/reports"] },
  ];
}

function workspaceTabFromPath(pathname: string, tabParam: string | null): "research" | "compare" | "journal" {
  if (pathname === "/trades") return "journal";
  if (pathname !== "/workspace" && !pathname.startsWith("/workspace/")) return "research";
  if (tabParam === "compare") return "compare";
  if (tabParam === "journal") return "journal";
  return "research";
}

function isActive(
  pathname: string,
  href: string,
  workspaceTab: "research" | "compare" | "journal",
  match?: readonly string[],
  linkWorkspaceTab?: NavLink["workspaceTab"]
) {
  if (linkWorkspaceTab) {
    const prefixes = match ?? ["/workspace"];
    const onWorkspace = prefixes.some(
      (p) => pathname === p || pathname.startsWith(p + "/")
    );
    if (!onWorkspace) return false;
    return workspaceTab === linkWorkspaceTab;
  }

  if (pathname === href) return true;
  const prefixes = match ?? [href];
  return prefixes.some((p) => pathname === p || pathname.startsWith(p + "/"));
}

function NavTabs() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const { t } = useTranslation();
  const links = useNavLinks();
  const workspaceTab = workspaceTabFromPath(pathname, searchParams.get("tab"));

  return (
    <AppTabBar aria-label={t.navAria.main} className="app-nav-tabs">
      {links.map((link) => (
        <AppTabLink
          key={link.href}
          href={link.href}
          active={isActive(pathname, link.href, workspaceTab, link.match, link.workspaceTab)}
        >
          {link.label}
        </AppTabLink>
      ))}
    </AppTabBar>
  );
}

function NavTabsFallback() {
  const links = useNavLinks();
  const pathname = usePathname();
  const { t } = useTranslation();

  return (
    <AppTabBar aria-label={t.navAria.main} className="app-nav-tabs">
      {links.map((link) => (
        <AppTabLink
          key={link.href}
          href={link.href}
          active={pathname === link.href || (link.match?.includes(pathname) ?? false)}
        >
          {link.label}
        </AppTabLink>
      ))}
    </AppTabBar>
  );
}

export function Nav() {
  return (
    <>
      <header className="app-nav sticky top-0 z-40">
        <div className="app-nav-inner">
          <Link href="/" className="app-brand" aria-label="Home">
            <span className="app-brand-mark" aria-hidden />
            <span className="app-brand-text">
              <span className="app-brand-name">Picker</span>
              <span className="app-brand-sub">Quant</span>
            </span>
          </Link>

          <div className="app-nav-center">
            <Suspense fallback={<NavTabsFallback />}>
              <NavTabs />
            </Suspense>
          </div>

          <div className="app-nav-actions">
            <SettingsMenu />
            <CommandPaletteTrigger />
          </div>
        </div>
      </header>
      <CommandPalette />
    </>
  );
}
