"use client";

import clsx from "clsx";
import Link from "next/link";
import type { PortfolioDecisionItem } from "@/lib/types";
import {
  actionSummary,
  formatCurrency,
  formatShares,
  rowAccentClass,
} from "@/lib/dailyDecisionUtils";
import { useTranslation } from "@/lib/i18n";
import { PercentText } from "@/components/ui/typography";
import { DecisionBadge } from "./DecisionBadge";
import { DecisionMixBar } from "./DecisionMixBar";
import { HoldingWhyDrawer } from "./HoldingWhyDrawer";

function PositionCell({ item }: { item: PortfolioDecisionItem }) {
  const { t } = useTranslation();
  const priceLabel = item.price_available === false ? "—" : formatCurrency(item.price);
  const bucketLabel =
    item.bucket === "penny" ? t.buckets.penny.label : item.bucket === "compounder" ? t.buckets.compounder.label : null;

  return (
    <div className="min-w-[140px]">
      <div className="flex items-center gap-2">
        <p className="text-base font-semibold text-zinc-50">{item.symbol}</p>
        {bucketLabel && (
          <span className="rounded-md border border-white/5 bg-zinc-800 px-1.5 py-0.5 text-[10px] font-medium text-zinc-300">
            {bucketLabel}
          </span>
        )}
      </div>
      <p className="mt-1 text-sm text-secondary">
        <span className="finance-value">{formatShares(item.shares)}</span> {t.home.dailySharesLabel}
        <span className="mx-1.5 text-zinc-600">·</span>
        <span className="finance-value font-medium text-zinc-100">{formatCurrency(item.market_value)}</span>
      </p>
      <p className="mt-0.5 text-xs text-tertiary">
        {formatCurrency(item.avg_cost)} → {priceLabel}
      </p>
    </div>
  );
}

function Chevron({ open }: { open: boolean }) {
  return (
    <svg
      className={clsx("h-4 w-4 text-tertiary transition-transform", open && "rotate-180")}
      viewBox="0 0 20 20"
      fill="currentColor"
      aria-hidden
    >
      <path
        fillRule="evenodd"
        d="M5.23 7.21a.75.75 0 011.06.02L10 10.94l3.71-3.71a.75.75 0 111.06 1.06l-4.24 4.25a.75.75 0 01-1.06 0L5.21 8.29a.75.75 0 01.02-1.08z"
        clipRule="evenodd"
      />
    </svg>
  );
}

export function HoldingDecisionRowDesktop({
  item,
  expanded,
  onToggle,
}: {
  item: PortfolioDecisionItem;
  expanded: boolean;
  onToggle: () => void;
}) {
  const { t } = useTranslation();
  return (
    <>
      <tr
        className={clsx("cursor-pointer border-b border-white/5", rowAccentClass(item.decision))}
        onClick={onToggle}
        onKeyDown={(e) => e.key === "Enter" && onToggle()}
        tabIndex={0}
        aria-expanded={expanded}
      >
        <td>
          <Link href={`/workspace?symbol=${item.symbol}`} onClick={(e) => e.stopPropagation()} className="block">
            <PositionCell item={item} />
          </Link>
        </td>
        <td className="text-right">
          <PercentText value={item.pl_pct} />
        </td>
        <td className="text-right">
          <span className="finance-value text-sm font-medium text-zinc-100">{item.current_weight.toFixed(1)}%</span>
          <span className="mt-0.5 block text-xs text-tertiary">
            {t.home.dailyTargetShort} {item.target_weight.toFixed(1)}%
          </span>
        </td>
        <td className="min-w-[148px]">
          <DecisionMixBar buyPct={item.buy_pct} keepPct={item.keep_pct} sellPct={item.sell_pct} layout="grid" />
        </td>
        <td>
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <DecisionBadge decision={item.decision} size="md" />
              <p className="mt-1.5 line-clamp-2 text-xs leading-relaxed text-secondary">{actionSummary(item)}</p>
            </div>
            <button
              type="button"
              className="mt-0.5 shrink-0 rounded-md p-1 hover:bg-zinc-800/80"
              aria-label={expanded ? t.home.dailyHideWhy : t.home.dailyShowWhy}
              onClick={(e) => {
                e.stopPropagation();
                onToggle();
              }}
            >
              <Chevron open={expanded} />
            </button>
          </div>
        </td>
      </tr>
      {expanded && (
        <tr>
          <td colSpan={5} className="border-b border-white/5 bg-zinc-950/50 px-4 pb-4 pt-1">
            <HoldingWhyDrawer item={item} />
          </td>
        </tr>
      )}
    </>
  );
}

export function HoldingDecisionRowMobile({
  item,
  expanded,
  onToggle,
}: {
  item: PortfolioDecisionItem;
  expanded: boolean;
  onToggle: () => void;
}) {
  const { t } = useTranslation();

  return (
    <div className={clsx("app-card p-4", rowAccentClass(item.decision))}>
      <div className="flex items-start justify-between gap-3">
        <button type="button" className="min-w-0 flex-1 text-left" onClick={onToggle}>
          <PositionCell item={item} />
        </button>
        <DecisionBadge decision={item.decision} size="md" />
      </div>
      <div className="mt-3 flex items-center justify-between gap-3">
        <PercentText value={item.pl_pct} />
        <span className="finance-value text-sm text-secondary">
          {item.current_weight.toFixed(1)}% · tgt {item.target_weight.toFixed(1)}%
        </span>
      </div>
      <DecisionMixBar className="mt-3" buyPct={item.buy_pct} keepPct={item.keep_pct} sellPct={item.sell_pct} />
      <p className="mt-2 text-sm leading-relaxed text-secondary">{actionSummary(item)}</p>
      <button
        type="button"
        className="mt-2 flex items-center gap-1 text-xs font-medium text-tertiary hover:text-zinc-200"
        onClick={onToggle}
      >
        <Chevron open={expanded} />
        {expanded ? t.home.dailyHideWhy : t.home.dailyShowWhy}
      </button>
      {expanded && (
        <div className="mt-3 border-t border-white/5 pt-3">
          <HoldingWhyDrawer item={item} />
        </div>
      )}
    </div>
  );
}

export function ActiveHoldingsDecisionTable({
  items,
  expanded,
  onToggle,
}: {
  items: PortfolioDecisionItem[];
  expanded: string | null;
  onToggle: (symbol: string) => void;
}) {
  const { t } = useTranslation();

  if (!items.length) {
    return (
      <p className="rounded-xl border border-dashed border-white/10 px-4 py-10 text-center text-sm text-secondary">
        {t.home.dailyNoDecision}
      </p>
    );
  }

  return (
    <>
      <div className="hidden overflow-hidden rounded-xl border border-white/8 md:block">
        <table className="home-holdings-table w-full text-left text-sm">
          <thead>
            <tr className="border-b border-white/8 bg-zinc-900/50">
              <th className="px-4 py-3">{t.home.dailyColPosition}</th>
              <th className="px-4 py-3 text-right">{t.home.dailyColPl}</th>
              <th className="px-4 py-3 text-right">{t.home.dailyColWeight}</th>
              <th className="px-4 py-3">{t.home.dailyColDecisionMix}</th>
              <th className="px-4 py-3">{t.home.dailyColDecision}</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <HoldingDecisionRowDesktop
                key={item.symbol}
                item={item}
                expanded={expanded === item.symbol}
                onToggle={() => onToggle(item.symbol)}
              />
            ))}
          </tbody>
        </table>
      </div>
      <div className="space-y-3 md:hidden">
        {items.map((item) => (
          <HoldingDecisionRowMobile
            key={item.symbol}
            item={item}
            expanded={expanded === item.symbol}
            onToggle={() => onToggle(item.symbol)}
          />
        ))}
      </div>
    </>
  );
}
