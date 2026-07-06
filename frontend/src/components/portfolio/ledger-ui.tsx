"use client";

import clsx from "clsx";

/** Compact inputs for ledger table cells and add-row form. */
export const ledgerInputClass = "input-field input-field--dense";

export const ledgerSelectClass = clsx(ledgerInputClass, "cursor-pointer appearance-none pr-8");

export function LedgerInset({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return <div className={clsx("ledger-inset", className)}>{children}</div>;
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
    <label className={clsx("ledger-form-field block", className)}>
      <span className="ledger-form-field__label">{label}</span>
      {children}
      {hint && <span className="ledger-form-field__hint">{hint}</span>}
    </label>
  );
}

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
    <div className={clsx("ledger-side-toggle", className)} role="group" aria-label={`${buyLabel} / ${sellLabel}`}>
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
        "inline-flex items-center rounded-md border px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide",
        variant === "saved"
          ? "border-buy/40 bg-buy/15 text-buy"
          : "border-amber-500/40 bg-amber-500/15 text-amber-200"
      )}
    >
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
        <p className="text-xs text-tertiary">{emptyLabel}</p>
      ) : (
        <ul className="flex flex-wrap gap-2">
          {holdings.map((h) => (
            <li key={h.symbol} className="chip ledger-holding-chip tabular-nums px-2.5 py-1">
              <span className="font-semibold text-symbol">{h.symbol}</span>
              <span className="text-secondary">{h.shares}</span>
              <span className="text-secondary">@${h.avg_cost.toFixed(2)}</span>
            </li>
          ))}
        </ul>
      )}
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
        "inline-flex rounded-md border px-2 py-0.5 text-[11px] font-semibold capitalize",
        isBuy && "border-buy/40 bg-buy/15 text-buy",
        isSell && "border-red-500/40 bg-red-500/15 text-negative",
        !isBuy && !isSell && "border-white/10 bg-zinc-800/60 text-secondary"
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
        "btn-ghost rounded-lg px-2.5 py-1 text-[11px] font-medium",
        variant === "save"
          ? "border-buy/35 text-buy hover:bg-buy/10"
          : "border-red-500/25 text-negative hover:bg-red-500/10",
        className
      )}
      {...props}
    >
      {children}
    </button>
  );
}
