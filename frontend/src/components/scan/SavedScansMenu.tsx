"use client";

import { formatDateTime } from "@/lib/datetime";
import { fmt, useTranslation } from "@/lib/i18n";
import type { SavedScanItem } from "@/lib/types";
import clsx from "clsx";
import { useEffect, useRef, useState } from "react";

interface SavedScansMenuProps {
  scans: SavedScanItem[];
  onLoad: (scan: SavedScanItem) => void;
  onDelete: (scanId: number) => void;
}

export function SavedScansMenu({ scans, onLoad, onDelete }: SavedScansMenuProps) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [menuId, setMenuId] = useState<number | null>(null);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) {
        setOpen(false);
        setMenuId(null);
      }
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  if (scans.length === 0) {
    return (
      <span className="scan-command-bar__btn scan-command-bar__btn--disabled" title={t.scan.noSavedScans}>
        {t.scan.savedScansMenu}
      </span>
    );
  }

  return (
    <div className="relative" ref={rootRef}>
      <button
        type="button"
        className={clsx("scan-command-bar__btn", open && "scan-command-bar__btn--active")}
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-haspopup="listbox"
      >
        {t.scan.savedScansMenu}
        <span className="scan-command-bar__badge">{scans.length}</span>
      </button>
      {open && (
        <ul className="saved-scans-menu" role="listbox">
          {scans.map((s) => (
            <li key={s.id} className="saved-scans-menu__item">
              <button
                type="button"
                className="saved-scans-menu__load"
                onClick={() => {
                  onLoad(s);
                  setOpen(false);
                }}
              >
                <span className="saved-scans-menu__name">{s.name}</span>
                <span className="saved-scans-menu__meta">
                  {fmt(t.library.resultCount, { bucket: s.bucket, count: s.result_count })}
                  {s.completed_at || s.created_at
                    ? ` · ${formatDateTime(s.completed_at ?? s.created_at ?? "")}`
                    : ""}
                </span>
              </button>
              <div className="relative">
                <button
                  type="button"
                  className="saved-scans-menu__more"
                  aria-label={t.scan.savedScanActions}
                  onClick={() => setMenuId(menuId === s.id ? null : s.id)}
                >
                  ⋯
                </button>
                {menuId === s.id && (
                  <div className="saved-scans-menu__overflow">
                    <button
                      type="button"
                      className="saved-scans-menu__delete"
                      onClick={() => {
                        void onDelete(s.id);
                        setMenuId(null);
                      }}
                    >
                      {t.common.delete}
                    </button>
                  </div>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
