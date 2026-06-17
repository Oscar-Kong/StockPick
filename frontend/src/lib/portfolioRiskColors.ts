/** Analytical color scales for Portfolio → Risk tab (dark theme). */

export type RiskSeverity = "low" | "moderate" | "elevated" | "high";

export function betaSeverity(beta: number | null | undefined): RiskSeverity {
  if (beta == null || Number.isNaN(beta)) return "moderate";
  if (beta < 0.85) return "low";
  if (beta <= 1.15) return "moderate";
  if (beta <= 1.35) return "elevated";
  return "high";
}

export function betaTextClass(beta: number | null | undefined): string {
  switch (betaSeverity(beta)) {
    case "low":
      return "text-sky-400";
    case "moderate":
      return "text-zinc-200";
    case "elevated":
      return "text-amber-400";
    case "high":
      return "text-red-400";
  }
}

export function betaBadgeClass(beta: number | null | undefined): string {
  switch (betaSeverity(beta)) {
    case "low":
      return "border-sky-500/30 bg-sky-500/10 text-sky-300";
    case "moderate":
      return "border-zinc-600/40 bg-zinc-800/60 text-zinc-200";
    case "elevated":
      return "border-amber-500/35 bg-amber-500/10 text-amber-200";
    case "high":
      return "border-red-500/35 bg-red-500/10 text-red-300";
  }
}

export function concentrationSeverity(weight: number | null | undefined): RiskSeverity {
  if (weight == null || Number.isNaN(weight)) return "moderate";
  if (weight < 0.15) return "low";
  if (weight <= 0.25) return "elevated";
  return "high";
}

export function concentrationTextClass(weight: number | null | undefined): string {
  switch (concentrationSeverity(weight)) {
    case "low":
      return "text-[#7dff8e]";
    case "moderate":
      return "text-zinc-200";
    case "elevated":
      return "text-amber-400";
    case "high":
      return "text-red-400";
  }
}

export function concentrationBarClass(weight: number | null | undefined): string {
  switch (concentrationSeverity(weight)) {
    case "low":
      return "bg-[#7dff8e]";
    case "moderate":
      return "bg-zinc-500";
    case "elevated":
      return "bg-amber-500";
    case "high":
      return "bg-red-500";
  }
}

export function pcVarianceSeverity(ratio: number, index: number): RiskSeverity {
  if (index === 0 && ratio >= 0.45) return "high";
  if (index === 0 && ratio >= 0.35) return "elevated";
  if (ratio >= 0.25) return "moderate";
  return "low";
}

export function pcVarianceChipClass(ratio: number, index: number): string {
  switch (pcVarianceSeverity(ratio, index)) {
    case "low":
      return "border-sky-500/25 bg-sky-500/10 text-sky-200";
    case "moderate":
      return "border-zinc-600/40 bg-zinc-800/50 text-zinc-300";
    case "elevated":
      return "border-amber-500/30 bg-amber-500/10 text-amber-200";
    case "high":
      return "border-red-500/35 bg-red-500/10 text-red-200";
  }
}

export function pcVarianceBarClass(ratio: number, index: number): string {
  switch (pcVarianceSeverity(ratio, index)) {
    case "low":
      return "bg-sky-500";
    case "moderate":
      return "bg-zinc-500";
    case "elevated":
      return "bg-amber-500";
    case "high":
      return "bg-red-500";
  }
}

export function correlationCellClass(value: number | null | undefined, isDiagonal: boolean): string {
  if (isDiagonal) return "bg-zinc-800/80 text-zinc-500";
  if (value == null || Number.isNaN(value)) return "bg-zinc-900/50 text-zinc-600";
  const v = Math.abs(value);
  if (v >= 0.85) return "bg-red-500/40 text-red-100";
  if (v >= 0.7) return "bg-orange-500/30 text-orange-100";
  if (v >= 0.55) return "bg-amber-500/22 text-amber-100";
  if (v >= 0.4) return "bg-zinc-700/45 text-zinc-300";
  if (v >= 0.25) return "bg-sky-500/12 text-sky-200";
  return "bg-emerald-500/10 text-emerald-200";
}

export function loadingValueClass(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "text-zinc-500";
  if (value >= 0.35) return "text-red-300";
  if (value >= 0.2) return "text-amber-300";
  if (value <= -0.2) return "text-sky-300";
  return "text-zinc-300";
}

export function effectiveBetsSeverity(n: number): RiskSeverity {
  if (n >= 8) return "low";
  if (n >= 5) return "moderate";
  if (n >= 3) return "elevated";
  return "high";
}

export function effectiveBetsTextClass(n: number): string {
  switch (effectiveBetsSeverity(n)) {
    case "low":
      return "text-[#7dff8e]";
    case "moderate":
      return "text-zinc-200";
    case "elevated":
      return "text-amber-400";
    case "high":
      return "text-red-400";
  }
}

/** Herfindahl index and effective number of bets from position weights. */
export function concentrationStats(weights: number[]): { hhi: number; effectiveBets: number } {
  const valid = weights.filter((w) => w > 0);
  if (!valid.length) return { hhi: 0, effectiveBets: 0 };
  const hhi = valid.reduce((s, w) => s + w * w, 0);
  return { hhi, effectiveBets: hhi > 0 ? 1 / hhi : 0 };
}
