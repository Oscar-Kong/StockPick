/** Format penny scan liquidity metrics for display (raw ratios vs scores). */

export type PennyLiquidityDisplay = {
  relativeVolume?: string;
  volumeSignalScore?: string;
  averageDollarVolume?: string;
  atr?: string;
  gap?: string;
  spread?: string;
  warnings: string[];
};

function asNumber(value: unknown): number | undefined {
  if (value == null || value === "") return undefined;
  const n = Number(value);
  return Number.isFinite(n) ? n : undefined;
}

export function formatPennyLiquidity(metrics: Record<string, unknown> | undefined): PennyLiquidityDisplay {
  const m = metrics ?? {};
  const out: PennyLiquidityDisplay = { warnings: [] };

  const ratio = asNumber(m.relative_volume_ratio) ?? asNumber(m.volume_ratio);
  if (ratio != null) out.relativeVolume = `${ratio.toFixed(1)}x`;

  const volScore = asNumber(m.relative_volume_score) ?? asNumber(m.volume_signal_score);
  if (volScore != null) out.volumeSignalScore = `${Math.round(volScore)}/100`;

  const adv = asNumber(m.average_dollar_volume_20d);
  if (adv != null) {
    out.averageDollarVolume = adv >= 1_000_000 ? `$${(adv / 1_000_000).toFixed(1)}M` : `$${Math.round(adv).toLocaleString()}`;
  }

  const atr = asNumber(m.atr_percent);
  if (atr != null) out.atr = `${atr.toFixed(1)}%`;

  const gap = asNumber(m.gap_percent);
  if (gap != null) out.gap = `${gap >= 0 ? "+" : ""}${gap.toFixed(1)}%`;

  const spread = asNumber(m.spread_estimate_pct);
  if (spread != null) out.spread = `${spread.toFixed(1)}%`;

  const rawWarnings = m.liquidity_warnings ?? m.dilution_warnings;
  if (Array.isArray(rawWarnings)) {
    out.warnings = rawWarnings.filter((w): w is string => typeof w === "string");
  }

  return out;
}

export function hasPennyLiquidityMetrics(metrics: Record<string, unknown> | undefined): boolean {
  const d = formatPennyLiquidity(metrics);
  return Boolean(d.relativeVolume || d.volumeSignalScore || d.averageDollarVolume || d.atr);
}
