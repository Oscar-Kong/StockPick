import clsx from "clsx";
import { formatDecision, getDecisionTone } from "@/lib/dailyDecisionUtils";

const STYLES = {
  buy: "text-buy border-buy/40 bg-buy/15",
  keep: "text-zinc-200 border-zinc-600/50 bg-zinc-800/60",
  sell: "text-negative border-red-500/40 bg-red-500/15",
  review: "text-amber-200 border-amber-500/40 bg-amber-500/15",
} as const;

export function DecisionBadge({ decision, size = "sm" }: { decision: string; size?: "sm" | "md" }) {
  const tone = getDecisionTone(decision);
  return (
    <span
      className={clsx(
        "inline-flex items-center rounded-md border font-semibold uppercase tracking-wide",
        STYLES[tone],
        size === "md" ? "px-2.5 py-1 text-xs" : "px-2 py-0.5 text-sm"
      )}
    >
      {formatDecision(decision)}
    </span>
  );
}
