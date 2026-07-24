import type { StockResult } from "@/lib/types";

export type ScanTradeHint = {
  recommendation: string;
  buyPct: number;
  waitPct: number;
  reason: string;
};

function riskWaitBonus(level: string): number {
  if (level === "low") return 0;
  if (level === "high") return 28;
  return 12;
}

function labelFromScore(score: number): string {
  if (score >= 80) return "strong_buy";
  if (score >= 65) return "buy";
  if (score >= 50) return "watch";
  if (score >= 35) return "hold";
  return "avoid";
}

/** Client fallback when cached scan rows predate trade-hint metrics. */
export function deriveScanTradeHint(stock: StockResult): ScanTradeHint {
  const score = Math.max(0, Math.min(100, stock.score));
  const sleeve = stock.bucket;
  const risk = stock.risk_level;
  const metrics = stock.metrics ?? {};
  const dq = metrics.data_quality_score as number | undefined;
  const earningsSoon = Boolean(stock.earnings_soon ?? metrics.earnings_soon);
  const providerLimited = Boolean(metrics.provider_limited_partial_data);
  const fallbackReason =
    typeof metrics.fallback_reason === "string" ? metrics.fallback_reason : "";
  const nonProviderFallback =
    Boolean(fallbackReason) &&
    fallbackReason !== "none" &&
    !providerLimited;

  let buyRaw = Math.max(0, (score - 35) * 1.4);
  let waitRaw = Math.max(5, 100 - score * 0.85) + riskWaitBonus(risk);

  if (earningsSoon) {
    waitRaw += 15;
    buyRaw *= 0.75;
  }
  if (providerLimited) {
    waitRaw += 20;
    buyRaw *= 0.6;
  } else if (nonProviderFallback) {
    waitRaw += 12;
    buyRaw *= 0.75;
  }
  if (dq != null) {
    if (dq < 50) {
      buyRaw *= 0.55;
      waitRaw += 18;
    }
    if (dq < 35) {
      buyRaw *= 0.3;
      waitRaw += 25;
    }
  }
  if (sleeve === "penny") {
    if (score < 58) {
      buyRaw *= 0.5;
      waitRaw += 10;
    }
    if (risk === "high") buyRaw *= 0.65;
  } else if (sleeve === "compounder" && score < 62) {
    buyRaw *= 0.45;
    waitRaw += 8;
  }

  const total = buyRaw + waitRaw || 1;
  const buyPct = Math.round((100 * buyRaw) / total * 10) / 10;
  const waitPct = Math.round((100 - buyPct) * 10) / 10;

  let recommendation = labelFromScore(score);
  let reason = "Mixed signals — patience";
  if (dq != null && dq < 35) {
    recommendation = "high_risk_no_decision";
    reason = "Insufficient data quality";
  } else if (providerLimited && (recommendation === "strong_buy" || recommendation === "buy")) {
    recommendation = "watch";
    reason = "Partial provider data";
  } else if (
    nonProviderFallback &&
    (recommendation === "strong_buy" || recommendation === "buy")
  ) {
    recommendation = "watch";
    reason = "Fallback ranking — verify filters";
  } else if (dq != null && dq < 50 && (recommendation === "strong_buy" || recommendation === "buy")) {
    recommendation = "watch";
    reason = "Low data quality";
  } else if (recommendation === "strong_buy" || recommendation === "buy") {
    reason = `Score ${score.toFixed(0)} supports entry`;
  } else if (recommendation === "watch") {
    reason = "Setup forming — confirm before sizing";
  } else if (recommendation === "avoid") {
    reason = "Weak score — skip for now";
  }

  return { recommendation, buyPct, waitPct, reason };
}

export function getScanTradeHint(stock: StockResult): ScanTradeHint {
  const metrics = stock.metrics ?? {};
  const buyPct = metrics.buy_pct as number | undefined;
  const waitPct = metrics.wait_pct as number | undefined;
  const recommendation = metrics.recommendation as string | undefined;
  const reason = metrics.trade_hint_reason as string | undefined;

  if (
    typeof buyPct === "number" &&
    typeof waitPct === "number" &&
    recommendation &&
    typeof reason === "string"
  ) {
    return { recommendation, buyPct, waitPct, reason };
  }
  return deriveScanTradeHint(stock);
}
