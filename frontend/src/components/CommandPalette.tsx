"use client";

import { useTranslation } from "@/lib/i18n";
import clsx from "clsx";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";

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

const FOCUSABLE =
  'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

export function CommandPalette() {
  const router = useRouter();
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const dialogRef = useRef<HTMLDivElement>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);
  const listboxId = useId();
  const liveId = useId();

  const close = useCallback(() => {
    setOpen(false);
    setQuery("");
  }, []);

  const go = useCallback(
    (href: string) => {
      close();
      router.push(href);
    },
    [close, router]
  );

  const staticItems: CommandItem[] = useMemo(
    () => [
      { id: "portfolio", label: t.nav.portfolio, hint: t.portfolio.workspaceSubtitle, href: "/", group: t.command.go },
      {
        id: "portfolio-research",
        label: t.portfolio.tabResearch,
        hint: t.portfolio.researchBasketHint,
        href: "/?tab=research",
        group: t.command.go,
      },
      {
        id: "workspace",
        label: t.nav.workspace,
        hint: t.command.researchWorkspace,
        href: "/workspace",
        group: t.command.go,
      },
      { id: "scan", label: t.nav.scan, hint: t.nav.scan, href: "/scan", group: t.command.go },
      { id: "quant-lab", label: t.nav.quantLab, hint: t.home.routeQuantLabHint, href: "/quant-lab", group: t.command.go },
      { id: "library", label: t.nav.library, hint: t.nav.library, href: "/library", group: t.command.go },
      { id: "settings", label: t.nav.settings, hint: t.settings.apiSettingsDesc, href: "/settings", group: t.command.go },
      { id: "intel", label: t.command.traderIntel, href: "/trader-intel", group: t.command.go },
      { id: "journal", label: t.portfolio.ledgerTitle, href: "/?tab=activity", group: t.command.go },
      { id: "penny", label: t.command.scanPenny, href: "/scan?bucket=penny", group: t.command.screens },
      { id: "compound", label: t.command.scanCompound, href: "/scan?bucket=compounder", group: t.command.screens },
    ],
    [t]
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
      previousFocusRef.current = document.activeElement as HTMLElement | null;
      setQuery("");
      setActive(0);
      requestAnimationFrame(() => inputRef.current?.focus());
    } else {
      requestAnimationFrame(() => previousFocusRef.current?.focus());
    }
  }, [open]);

  useEffect(() => {
    setActive(0);
  }, [query]);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        e.stopPropagation();
        close();
        return;
      }
      if (e.key !== "Tab" || !dialogRef.current) return;
      const nodes = [...dialogRef.current.querySelectorAll<HTMLElement>(FOCUSABLE)].filter(
        (el) => el.offsetParent !== null
      );
      if (!nodes.length) return;
      const first = nodes[0];
      const last = nodes[nodes.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKeyDown, true);
    return () => document.removeEventListener("keydown", onKeyDown, true);
  }, [open, close]);

  const run = (item: CommandItem) => {
    if (item.href) go(item.href);
    else item.action?.();
    close();
  };

  const activeItem = items[active];
  const activeOptionId = activeItem ? `command-option-${activeItem.id}` : undefined;

  if (!open) return null;

  return (
    <div
      className="command-overlay"
      role="presentation"
      onClick={close}
    >
      <div
        ref={dialogRef}
        className="command-dialog"
        role="dialog"
        aria-modal="true"
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
            role="combobox"
            aria-expanded
            aria-controls={listboxId}
            aria-activedescendant={activeOptionId}
            aria-autocomplete="list"
            onKeyDown={(e) => {
              if (e.key === "ArrowDown") {
                e.preventDefault();
                setActive((i) => Math.min(i + 1, Math.max(items.length - 1, 0)));
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
        <p id={liveId} className="sr-only" aria-live="polite" aria-atomic="true">
          {activeItem
            ? `${activeItem.label}${activeItem.hint ? `, ${activeItem.hint}` : ""}`
            : t.command.noMatches}
        </p>
        <ul id={listboxId} className="command-list" role="listbox" aria-label={t.command.menuLabel}>
          {items.length === 0 ? (
            <li className="command-empty" role="presentation">
              {t.command.noMatches}
            </li>
          ) : (
            items.map((item, idx) => (
              <li key={item.id} role="presentation">
                <button
                  type="button"
                  id={`command-option-${item.id}`}
                  role="option"
                  aria-selected={idx === active}
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
      className="command-trigger command-trigger--mobile"
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
