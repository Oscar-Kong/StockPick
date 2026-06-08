"use client";

import { useTranslation } from "@/lib/i18n";
import clsx from "clsx";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

type CommandItem = {
  id: string;
  label: string;
  hint?: string;
  href?: string;
  action?: () => void;
  group: string;
};

export function openCommandPalette() {
  window.dispatchEvent(new CustomEvent("open-command-palette"));
}

export function CommandPalette() {
  const router = useRouter();
  const { t, locale } = useTranslation();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const go = useCallback(
    (href: string) => {
      setOpen(false);
      setQuery("");
      router.push(href);
    },
    [router]
  );

  const staticItems: CommandItem[] = useMemo(
    () => [
      { id: "home", label: t.nav.home, hint: t.nav.home, href: "/", group: t.command.go },
      { id: "research", label: t.nav.research, hint: t.command.researchWorkspace, href: "/workspace", group: t.command.go },
      { id: "compare", label: t.command.comparePeers, hint: t.home.routeCompareHint, href: "/workspace?tab=compare", group: t.command.go },
      { id: "scan", label: t.nav.screen, hint: t.nav.screen, href: "/scan", group: t.command.go },
      { id: "portfolio", label: t.nav.portfolio, hint: t.nav.portfolio, href: "/portfolio", group: t.command.go },
      { id: "library", label: t.nav.library, hint: t.nav.library, href: "/library", group: t.command.go },
      { id: "settings", label: t.settings.apiSettings, hint: t.settings.apiSettingsDesc, href: "/settings", group: t.command.go },
      { id: "intel", label: t.command.traderIntel, href: "/trader-intel", group: t.command.go },
      { id: "penny", label: t.command.scanPenny, href: "/scan?bucket=penny", group: t.command.screens },
      { id: "medium", label: t.command.scanMedium, href: "/scan?bucket=medium", group: t.command.screens },
      { id: "compound", label: t.command.scanCompound, href: "/scan?bucket=compounder", group: t.command.screens },
      { id: "journal", label: t.command.tradeJournal, href: "/workspace?tab=journal", group: t.command.go },
    ],
    [t, locale]
  );

  const items = useMemo(() => {
    const q = query.trim().toUpperCase();
    if (q.length >= 1 && /^[A-Z][A-Z0-9.\-]{0,9}$/.test(q)) {
      return [
        {
          id: `sym-${q}`,
          label: t.command.openSymbol.replace("{symbol}", q),
          hint: t.command.researchWorkspace,
          href: `/workspace?symbol=${encodeURIComponent(q)}`,
          group: t.command.symbol,
        },
        ...staticItems,
      ];
    }
    if (!query.trim()) return staticItems;
    const lower = query.toLowerCase();
    return staticItems.filter(
      (i) =>
        i.label.toLowerCase().includes(lower) ||
        (i.hint || "").toLowerCase().includes(lower)
    );
  }, [query, staticItems, t]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((v) => !v);
        setActive(0);
      }
      if (e.key === "Escape") setOpen(false);
    };
    const onOpen = () => {
      setOpen(true);
      setActive(0);
    };
    window.addEventListener("keydown", onKey);
    window.addEventListener("open-command-palette", onOpen);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("open-command-palette", onOpen);
    };
  }, []);

  useEffect(() => {
    if (open) {
      setQuery("");
      setActive(0);
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [open]);

  useEffect(() => {
    setActive(0);
  }, [query]);

  const run = (item: CommandItem) => {
    if (item.href) go(item.href);
    else item.action?.();
    setOpen(false);
  };

  if (!open) return null;

  return (
    <div
      className="command-overlay"
      role="presentation"
      onClick={() => setOpen(false)}
    >
      <div
        className="command-dialog"
        role="dialog"
        aria-label={t.command.menuLabel}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="command-input-wrap">
          <span className="command-search-icon" aria-hidden>
            ⌕
          </span>
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t.command.placeholder}
            className="command-input"
            aria-label={t.command.placeholder}
            onKeyDown={(e) => {
              if (e.key === "ArrowDown") {
                e.preventDefault();
                setActive((i) => Math.min(i + 1, items.length - 1));
              }
              if (e.key === "ArrowUp") {
                e.preventDefault();
                setActive((i) => Math.max(i - 1, 0));
              }
              if (e.key === "Enter" && items[active]) {
                e.preventDefault();
                run(items[active]);
              }
            }}
          />
          <kbd className="command-kbd">esc</kbd>
        </div>
        <ul className="command-list">
          {items.length === 0 ? (
            <li className="command-empty">{t.command.noMatches}</li>
          ) : (
            items.map((item, idx) => (
              <li key={item.id}>
                <button
                  type="button"
                  className={clsx("command-row", idx === active && "command-row--active")}
                  onMouseEnter={() => setActive(idx)}
                  onClick={() => run(item)}
                >
                  <span className="command-row-label">{item.label}</span>
                  <span className="command-row-meta">
                    <span className="command-row-group">{item.group}</span>
                    {item.hint && <span className="command-row-hint">{item.hint}</span>}
                  </span>
                </button>
              </li>
            ))
          )}
        </ul>
        <p className="command-footer-hint">
          <kbd className="command-kbd">↑↓</kbd> {t.command.navHint}
        </p>
      </div>
    </div>
  );
}

/** Nav search trigger */
export function CommandPaletteTrigger() {
  const { t } = useTranslation();
  return (
    <button
      type="button"
      className="command-trigger"
      onClick={() => openCommandPalette()}
      aria-label={t.command.openMenu}
    >
      <span className="command-trigger-icon" aria-hidden>
        ⌕
      </span>
      <span className="command-trigger-text">{t.command.search}</span>
      <kbd className="command-trigger-kbd">⌘K</kbd>
    </button>
  );
}
