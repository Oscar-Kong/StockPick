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
    <section className={clsx("surface-card overflow-hidden", className)}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left hover:bg-zinc-900/40"
        aria-expanded={open}
      >
        <span>
          <span className="block text-sm font-medium text-zinc-200">{title}</span>
          {summary && !open && <span className="mt-0.5 block text-xs text-zinc-500">{summary}</span>}
        </span>
        <span className="text-zinc-500" aria-hidden>
          {open ? "−" : "+"}
        </span>
      </button>
      {open && <div className="border-t border-zinc-800 px-4 py-3">{children}</div>}
    </section>
  );
}
