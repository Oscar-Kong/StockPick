import Link from "next/link";
import { actionSummary, buildActionQueue } from "@/lib/dailyDecisionUtils";
import type { PortfolioDecisionItem } from "@/lib/types";
import { useTranslation } from "@/lib/i18n";
import { SectionCard } from "@/components/ui/AppCard";
import { DecisionBadge } from "./DecisionBadge";
import { DecisionMixBar } from "./DecisionMixBar";

export function DailyActionQueue({
  items,
  density = "default",
}: {
  items: PortfolioDecisionItem[];
  /** Single-column stack for portfolio sidebar layout */
  density?: "default" | "sidebar";
}) {
  const { t } = useTranslation();
  const queue = buildActionQueue(items);

  return (
    <SectionCard
      title={t.home.dailyActionQueueTitle}
      subtitle={t.home.dailyActionQueueSubtitle}
      variant="elevated"
      className="portfolio-action-queue"
    >
      {queue.length === 0 ? (
        <p className="portfolio-glass-inset px-4 py-5 text-sm text-secondary">
          {t.home.dailyActionQueueEmpty}
        </p>
      ) : (
        <ul
          className={
            density === "sidebar"
              ? "flex flex-col gap-3"
              : "grid gap-3 sm:grid-cols-2 xl:grid-cols-3"
          }
        >
          {queue.map((item) => (
            <li
              key={item.symbol}
              className="portfolio-action-item"
            >
              <div className="flex items-start justify-between gap-2">
                <Link href={`/workspace?symbol=${item.symbol}`} className="text-base text-symbol hover:underline">
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
