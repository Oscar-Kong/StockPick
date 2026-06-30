"use client";

import clsx from "clsx";

type Accent = "emerald" | "sky" | "amber";

const ACCENT_RING: Record<Accent, string> = {
  emerald:
    "from-emerald-500/40 via-zinc-800/60 to-sky-500/20 shadow-[0_0_24px_-8px_rgba(16,185,129,0.35)]",
  sky: "from-sky-500/35 via-zinc-800/60 to-violet-500/20 shadow-[0_0_24px_-8px_rgba(56,189,248,0.3)]",
  amber: "from-amber-500/30 via-zinc-800/60 to-orange-500/15 shadow-[0_0_20px_-8px_rgba(245,158,11,0.25)]",
};

export function LedgerGlassCard({
  children,
  className,
  accent = "emerald",
  innerClassName,
}: {
  children: React.ReactNode;
  className?: string;
  accent?: Accent;
  innerClassName?: string;
}) {
  return (
    <div
      className={clsx(
        "rounded-2xl bg-gradient-to-br p-px transition-shadow duration-300",
        ACCENT_RING[accent],
        className
      )}
    >
      <div
        className={clsx(
          "rounded-[calc(1rem-1px)] border border-white/[0.04] bg-zinc-950/80 backdrop-blur-md",
          innerClassName
        )}
      >
        {children}
      </div>
    </div>
  );
}

export function LedgerFormField({
  label,
  hint,
  children,
  className,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <label className={clsx("ledger-form-field group block", className)}>
      <span className="ledger-form-field__label">{label}</span>
      {children}
      {hint && <span className="ledger-form-field__hint">{hint}</span>}
    </label>
  );
}

export const ledgerInputClass =
  "ledger-input w-full min-w-0 rounded-xl border border-zinc-700/80 bg-zinc-900/70 px-3 py-2.5 text-sm text-zinc-100 shadow-inner shadow-black/20 outline-none transition-[border-color,box-shadow,background] placeholder:text-zinc-600 focus:border-primary/50 focus:bg-zinc-900/90 focus:ring-2 focus:ring-primary/15";

export const ledgerSelectClass = clsx(ledgerInputClass, "cursor-pointer appearance-none pr-8");

export function LedgerSideToggle({
  value,
  onChange,
  buyLabel,
  sellLabel,
  className,
}: {
  value: string;
  onChange: (side: "buy" | "sell") => void;
  buyLabel: string;
  sellLabel: string;
  className?: string;
}) {
  const isBuy = value.toLowerCase() === "buy";
  return (
    <div className={clsx("ledger-side-toggle", className)} role="group" aria-label={buyLabel + " / " + sellLabel}>
      <button
        type="button"
        className={clsx("ledger-side-toggle__btn", isBuy && "ledger-side-toggle__btn--buy-active")}
        aria-pressed={isBuy}
        onClick={() => onChange("buy")}
      >
        {buyLabel}
      </button>
      <button
        type="button"
        className={clsx("ledger-side-toggle__btn", !isBuy && "ledger-side-toggle__btn--sell-active")}
        aria-pressed={!isBuy}
        onClick={() => onChange("sell")}
      >
        {sellLabel}
      </button>
    </div>
  );
}

export function LedgerStatusBadge({
  variant,
  children,
}: {
  variant: "saved" | "draft";
  children: React.ReactNode;
}) {
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider",
        variant === "saved"
          ? "border border-emerald-500/30 bg-emerald-500/10 text-emerald-300 shadow-[0_0_12px_-4px_rgba(16,185,129,0.4)]"
          : "border border-amber-500/25 bg-amber-500/10 text-amber-200/90"
      )}
    >
      <span
        className={clsx(
          "h-1.5 w-1.5 rounded-full",
          variant === "saved" ? "bg-emerald-400" : "bg-amber-400 animate-pulse"
        )}
        aria-hidden
      />
      {children}
    </span>
  );
}

export function LedgerHoldingsStrip({
  title,
  holdings,
  emptyLabel = "—",
}: {
  title: string;
  holdings: Array<{ symbol: string; shares: number; avg_cost: number }>;
  emptyLabel?: string;
}) {
  return (
    <div className="ledger-holdings-strip">
      <p className="ledger-holdings-strip__title">{title}</p>
      {holdings.length === 0 ? (
        <p className="text-xs text-zinc-600">{emptyLabel}</p>
      ) : (
        <ul className="flex flex-wrap gap-2">
          {holdings.map((h) => (
            <li key={h.symbol} className="ledger-holding-chip tabular-nums">
              <span className="font-semibold text-zinc-100">{h.symbol}</span>
              <span className="text-zinc-500">{h.shares}</span>
              <span className="text-zinc-400">@${h.avg_cost.toFixed(2)}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function LedgerToolbar({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={clsx("flex flex-wrap items-center justify-end gap-2", className)}>{children}</div>;
}

export function LedgerToolbarButton({
  children,
  active,
  className,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { active?: boolean }) {
  return (
    <button
      type="button"
      className={clsx(
        "rounded-full border px-3 py-1.5 text-xs font-medium transition-all",
        active
          ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-200"
          : "border-zinc-700/80 bg-zinc-900/50 text-zinc-400 hover:border-zinc-600 hover:bg-zinc-800/60 hover:text-zinc-200",
        className
      )}
      {...props}
    >
      {children}
    </button>
  );
}

export function LedgerTableShell({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={clsx("ledger-table-shell overflow-x-auto rounded-2xl border border-zinc-800/80", className)}>
      {children}
    </div>
  );
}

export function LedgerSidePill({ side, label }: { side: string; label: string }) {
  const s = side.toLowerCase();
  const isBuy = s === "buy";
  const isSell = s === "sell";
  return (
    <span
      className={clsx(
        "inline-flex rounded-md px-1.5 py-0.5 text-[11px] font-medium capitalize",
        isBuy && "bg-emerald-500/15 text-emerald-300",
        isSell && "bg-red-500/15 text-red-300",
        !isBuy && !isSell && "bg-zinc-800 text-zinc-400"
      )}
    >
      {label}
    </span>
  );
}

export function LedgerActionButton({
  variant,
  children,
  className,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant: "save" | "delete" }) {
  return (
    <button
      type="button"
      className={clsx(
        "rounded-lg px-2.5 py-1 text-[11px] font-medium transition-all active:scale-[0.98]",
        variant === "save"
          ? "border border-emerald-500/35 bg-emerald-500/10 text-emerald-200 hover:bg-emerald-500/20 hover:shadow-[0_0_16px_-6px_rgba(16,185,129,0.5)]"
          : "border border-red-500/25 bg-red-500/5 text-red-300/90 hover:bg-red-500/15",
        className
      )}
      {...props}
    >
      {children}
    </button>
  );
}
