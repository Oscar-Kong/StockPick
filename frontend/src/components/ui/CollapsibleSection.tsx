"use client";

import clsx from "clsx";
import { useState } from "react";

interface CollapsibleSectionProps {
  title: string;
  summary?: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
  className?: string;
}

export function CollapsibleSection({
  title,
  summary,
  defaultOpen = false,
  children,
  className,
}: CollapsibleSectionProps) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <section className={clsx("app-card app-card--elevated overflow-hidden", className)}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="collapsible-section__trigger flex w-full items-center justify-between gap-3 px-5 py-4 text-left hover:bg-zinc-900/40"
        aria-expanded={open}
        aria-label={`${open ? "Collapse" : "Expand"} ${title}`}
      >
        <span>
          <span className="block text-sm font-semibold text-zinc-100">{title}</span>
          {summary && !open && <span className="mt-1 block text-xs text-secondary">{summary}</span>}
        </span>
        <span className="text-tertiary" aria-hidden>
          {open ? "−" : "+"}
        </span>
      </button>
      {open && <div className="collapsible-section__body border-t border-white/8 px-5 py-4">{children}</div>}
    </section>
  );
}
