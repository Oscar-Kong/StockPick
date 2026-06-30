import Link from "next/link";
import { actionSummary, buildActionQueue } from "@/lib/dailyDecisionUtils";
import type { PortfolioDecisionItem } from "@/lib/types";
import { useTranslation } from "@/lib/i18n";
import { SectionCard } from "@/components/ui/AppCard";
import { DecisionBadge } from "./DecisionBadge";
import { DecisionMixBar } from "./DecisionMixBar";

export function DailyActionQueue({ items }: { items: PortfolioDecisionItem[] }) {
  const { t } = useTranslation();
  const queue = buildActionQueue(items);

  return (
    <SectionCard title={t.home.dailyActionQueueTitle} subtitle={t.home.dailyActionQueueSubtitle} variant="elevated">
      {queue.length === 0 ? (
        <p className="rounded-xl border border-white/8 bg-zinc-900/40 px-4 py-5 text-sm text-secondary">
          {t.home.dailyActionQueueEmpty}
        </p>
      ) : (
        <ul className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {queue.map((item) => (
            <li
              key={item.symbol}
              className="rounded-xl border border-white/8 bg-zinc-900/35 px-4 py-3.5 transition-colors hover:border-brand/20 hover:bg-zinc-900/55"
            >
              <div className="flex items-start justify-between gap-2">
                <Link href={`/workspace?symbol=${item.symbol}`} className="text-base font-semibold text-primary hover:underline">
                  {item.symbol}
                </Link>
                <DecisionBadge decision={item.decision} />
              </div>
              <DecisionMixBar
                className="mt-3"
                buyPct={item.buy_pct}
                keepPct={item.keep_pct}
                sellPct={item.sell_pct}
                layout="inline"
              />
              <p className="mt-2 line-clamp-2 text-sm leading-relaxed text-secondary">{actionSummary(item)}</p>
              {item.risk_flags.length > 0 && (
                <p className="mt-1.5 text-xs font-medium text-amber-300">
                  {item.risk_flags.length} {t.home.dailyRiskFlagCount}
                </p>
              )}
            </li>
          ))}
        </ul>
      )}
    </SectionCard>
  );
}
