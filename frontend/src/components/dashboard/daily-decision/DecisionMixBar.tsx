import clsx from "clsx";
import { useTranslation } from "@/lib/i18n";

export function DecisionMixBar({
  buyPct,
  keepPct,
  sellPct,
  className,
  layout = "grid",
}: {
  buyPct: number;
  keepPct: number;
  sellPct: number;
  className?: string;
  /** grid = bar + 3 columns; inline = bar + single line */
  layout?: "grid" | "inline";
}) {
  const { t } = useTranslation();
  const total = buyPct + keepPct + sellPct || 1;
  const buy = (buyPct / total) * 100;
  const keep = (keepPct / total) * 100;
  const sell = (sellPct / total) * 100;

  return (
    <div className={clsx("space-y-2", className)}>
      <div className="flex h-3 overflow-hidden rounded-full bg-zinc-800">
        {buy > 0 && (
          <div
            className="bg-brand transition-all"
            style={{ width: `${buy}%` }}
            title={`${t.home.dailyMixBuy} ${buyPct.toFixed(0)}%`}
          />
        )}
        {keep > 0 && (
          <div
            className="decision-mix-keep transition-all"
            style={{ width: `${keep}%` }}
            title={`${t.home.dailyMixKeep} ${keepPct.toFixed(0)}%`}
          />
        )}
        {sell > 0 && (
          <div
            className="bg-negative transition-all"
            style={{ width: `${sell}%` }}
            title={`${t.home.dailyMixSell} ${sellPct.toFixed(0)}%`}
          />
        )}
      </div>

      {layout === "inline" ? (
        <p className="finance-value text-xs leading-snug">
          <span className="decision-mix-label-buy">{buyPct.toFixed(0)}% {t.home.dailyMixBuy}</span>
          <span className="mx-1.5 text-zinc-600">·</span>
          <span className="decision-mix-label-keep">{keepPct.toFixed(0)}% {t.home.dailyMixKeep}</span>
          <span className="mx-1.5 text-zinc-600">·</span>
          <span className="decision-mix-label-sell">{sellPct.toFixed(0)}% {t.home.dailyMixSell}</span>
        </p>
      ) : (
        <div className="grid grid-cols-3 gap-1 text-center text-xs">
          <span className="finance-value decision-mix-label-buy">
            {buyPct.toFixed(0)}% {t.home.dailyMixBuy}
          </span>
          <span className="finance-value decision-mix-label-keep">
            {keepPct.toFixed(0)}% {t.home.dailyMixKeep}
          </span>
          <span className="finance-value decision-mix-label-sell">
            {sellPct.toFixed(0)}% {t.home.dailyMixSell}
          </span>
        </div>
      )}
    </div>
  );
}
