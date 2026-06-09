import { factorPerformanceRows, primaryFactorHorizon } from "@/lib/quantLabNormalizers";
import { isFactorIcStale } from "@/lib/quantLabStability";
import {
  arePredictionOutcomesStale,
  countResolvedPredictions,
  countUnresolvedPredictions,
} from "@/lib/predictions";
import type {
  FactorPerformanceFactor,
  FactorPerformanceResponse,
  FeedbackSummaryResponse,
  PairsResearchResponse,
  PredictionSnapshotItem,
  QuantHealthSummary,
  SchedulerStatusResponse,
  V2AuditResponse,
  V2FactorsAdminResponse,
  V2VersionResponse,
  WalkForwardResearchResponse,
} from "@/lib/types";

export type ResearchReliabilityStatus =
  | "reliable"
  | "usable_with_warnings"
  | "weak_evidence"
  | "insufficient_data"
  | "stale"
  | "disabled"
  | "research_only";

export type FactorLifecycleStatus = "promote" | "keep" | "watch" | "retire" | "insufficient_evidence";

export interface ResearchReliabilityScore {
  status: ResearchReliabilityStatus;
  score_0_to_100: number;
  reasons: string[];
  warnings: string[];
  blockers: string[];
  suggested_next_action: string;
}

export interface WalkForwardOverfittingFlags {
  pbo_available: false;
  pbo_warning: string;
  warnings: string[];
}

export const PBO_NOT_IMPLEMENTED_WARNING = "pboNotImplemented";

function clampScore(score: number): number {
  return Math.max(0, Math.min(100, Math.round(score)));
}

function resolveStatus(
  score: number,
  opts: {
    disabled?: boolean;
    stale?: boolean;
    researchOnly?: boolean;
    blockers?: string[];
    warnings?: string[];
  }
): ResearchReliabilityStatus {
  if (opts.disabled) return "disabled";
  if (opts.blockers && opts.blockers.length > 0 && score < 35) return "insufficient_data";
  if (opts.stale) return "stale";
  if (score >= 80 && (opts.warnings?.length ?? 0) === 0 && (opts.blockers?.length ?? 0) === 0) {
    return "reliable";
  }
  if (score >= 55) return "usable_with_warnings";
  if (score >= 30) return "weak_evidence";
  if (opts.researchOnly) return "research_only";
  return "insufficient_data";
}

function finalize(
  score: number,
  reasons: string[],
  warnings: string[],
  blockers: string[],
  suggestedNextAction: string,
  opts: Parameters<typeof resolveStatus>[1] & { forceStatus?: ResearchReliabilityStatus } = {}
): ResearchReliabilityScore {
  const clamped = clampScore(score);
  const status = opts.forceStatus ?? resolveStatus(clamped, { ...opts, blockers, warnings });
  return {
    status,
    score_0_to_100: clamped,
    reasons,
    warnings,
    blockers,
    suggested_next_action: suggestedNextAction,
  };
}

export function computeFactorPerformanceReliability(input: {
  data: FactorPerformanceResponse | null;
  disabled?: boolean;
  loading?: boolean;
}): ResearchReliabilityScore {
  const { data, disabled, loading } = input;
  if (disabled) {
    return finalize(0, [], [], ["featureDisabled"], "enableV2", { disabled: true });
  }
  if (loading) {
    return finalize(50, ["loading"], [], [], "waitForLoad");
  }
  const factors = factorPerformanceRows(data);
  const icStale = isFactorIcStale(data?.as_of_date);
  const horizons = data?.horizons ?? [];
  const reasons: string[] = [];
  const warnings: string[] = [];
  const blockers: string[] = [];
  let score = 100;

  if (!data?.as_of_date || factors.length === 0) {
    blockers.push("noIcData");
    return finalize(15, reasons, warnings, blockers, "runIcPanel");
  }

  if (icStale) {
    warnings.push("icStale");
    score -= 25;
  }

  const samples = factors.map((f) => primaryFactorHorizon(f)?.sample_n ?? 0);
  const avgSample = samples.length ? samples.reduce((a, b) => a + b, 0) / samples.length : 0;
  const ics = factors
    .map((f) => primaryFactorHorizon(f)?.ic)
    .filter((v): v is number => v != null && Number.isFinite(v));
  const meanIc = ics.length ? ics.reduce((a, b) => a + b, 0) / ics.length : 0;

  reasons.push(`factorCount:${factors.length}`);
  if (factors.length >= 5) reasons.push("adequateFactorCoverage");
  if (avgSample >= 100) reasons.push("strongSampleSize");
  else if (avgSample >= 50) reasons.push("moderateSampleSize");

  if (factors.length < 3) {
    blockers.push("tooFewFactors");
    score -= 40;
  } else if (factors.length < 5) {
    warnings.push("limitedFactorCoverage");
    score -= 15;
  }

  if (avgSample < 30) {
    blockers.push("lowSampleSize");
    score -= 35;
  } else if (avgSample < 50) {
    warnings.push("borderlineSampleSize");
    score -= 15;
  }

  if (horizons.length === 0) {
    warnings.push("missingHorizons");
    score -= 10;
  }

  if (meanIc >= 0.03) reasons.push("positiveMeanIc");
  else if (meanIc < 0) {
    warnings.push("negativeMeanIc");
    score -= 20;
  }

  return finalize(score, reasons, warnings, blockers, icStale ? "runIcPanel" : "reviewFactorStatuses", {
    stale: icStale,
  });
}

export function computeFactorLifecycleStatus(
  factor: FactorPerformanceFactor,
  icStale: boolean
): FactorLifecycleStatus {
  const h = primaryFactorHorizon(factor);
  if (!h || h.sample_n == null || h.sample_n < 30) return "insufficient_evidence";
  const ic = h.ic;
  if (ic == null || !Number.isFinite(ic)) return "insufficient_evidence";
  if (icStale || h.sample_n < 50) return "watch";
  if (ic >= 0.05 && h.sample_n >= 100) return "promote";
  if (ic >= 0.02) return "keep";
  if (ic >= 0) return "watch";
  return "retire";
}

export function computeWalkForwardOverfittingWarnings(
  result: WalkForwardResearchResponse | null
): WalkForwardOverfittingFlags {
  const warnings: string[] = [PBO_NOT_IMPLEMENTED_WARNING];

  if (!result) {
    return { pbo_available: false, pbo_warning: PBO_NOT_IMPLEMENTED_WARNING, warnings };
  }

  const periods = result.periods_scored ?? 0;
  const windows = result.rebalance_periods ?? 0;

  if (periods < 5) warnings.push("tooFewScoredPeriods");
  if (windows < 5) warnings.push("tooFewWindows");
  if (periods > 0 && periods < 12) warnings.push("limitedOutOfSampleDepth");

  warnings.push("noTransactionCosts");
  warnings.push("noPurgedEmbargoValidation");
  warnings.push("noDeflatedSharpe");
  warnings.push("singleBestRunOnly");

  const agg = result.aggregate_horizons ?? {};
  const hasMetrics = Object.values(agg).some(
    (s) => s && typeof s === "object" && (s as Record<string, unknown>).periods
  );
  if (!hasMetrics && periods > 0) warnings.push("thinHorizonAggregates");

  return { pbo_available: false, pbo_warning: PBO_NOT_IMPLEMENTED_WARNING, warnings };
}

export function computeWalkForwardReliability(input: {
  result: WalkForwardResearchResponse | null;
  latestStale?: boolean;
  loading?: boolean;
}): ResearchReliabilityScore {
  const { result, latestStale, loading } = input;
  const overfit = computeWalkForwardOverfittingWarnings(result);
  const reasons: string[] = [];
  const warnings = [...overfit.warnings];
  const blockers: string[] = [];

  if (loading) {
    return finalize(40, ["loading"], warnings, [], "runWalkForward", { researchOnly: true });
  }

  if (!result || !result.run_id) {
    return finalize(
      20,
      [],
      warnings,
      ["noSavedRun"],
      "runWalkForward",
      { researchOnly: true, forceStatus: "research_only" }
    );
  }

  let score = 70;
  const periods = result.periods_scored ?? 0;
  const horizons = result.forward_horizons?.length ?? 0;

  if (periods >= 12) reasons.push("adequatePeriods");
  else if (periods >= 5) {
    warnings.push("moderatePeriods");
    score -= 15;
  } else {
    blockers.push("tooFewPeriods");
    score -= 35;
  }

  if (horizons >= 2) reasons.push("multipleHorizons");
  else {
    warnings.push("singleHorizon");
    score -= 10;
  }

  const agg = result.aggregate_horizons ?? {};
  for (const [, stats] of Object.entries(agg)) {
    if (!stats || typeof stats !== "object") continue;
    const s = stats as Record<string, unknown>;
    const rankIc = typeof s.mean_rank_ic === "number" ? s.mean_rank_ic : null;
    const hitRate = typeof s.mean_hit_rate === "number" ? s.mean_hit_rate : null;
    if (rankIc != null && rankIc >= 0.03) reasons.push("positiveRankIc");
    if (rankIc != null && rankIc < 0) {
      warnings.push("negativeRankIc");
      score -= 15;
    }
    if (hitRate != null && hitRate >= 0.52) reasons.push("favorableHitRate");
  }

  if (latestStale) {
    warnings.push("staleRun");
    score -= 20;
  }

  if (overfit.warnings.length >= 4) score -= 15;

  return finalize(score, reasons, warnings, blockers, "treatAsResearchOnly", {
    stale: latestStale,
    researchOnly: true,
  });
}

export function computePredictionsReliability(input: {
  predictions: PredictionSnapshotItem[];
  feedback: FeedbackSummaryResponse | null;
  disabled?: boolean;
  loading?: boolean;
}): ResearchReliabilityScore {
  const { predictions, feedback, disabled, loading } = input;
  if (disabled) {
    return finalize(0, [], [], ["featureDisabled"], "enablePredictions", { disabled: true });
  }
  if (loading) {
    return finalize(50, ["loading"], [], [], "waitForLoad");
  }

  const reasons: string[] = [];
  const warnings: string[] = [];
  const blockers: string[] = [];
  let score = 100;

  const resolved = countResolvedPredictions(predictions);
  const unresolved = countUnresolvedPredictions(predictions);
  const stale = arePredictionOutcomesStale(predictions, feedback);
  const outcomesCount = feedback?.outcomes_count ?? resolved;
  const meanErr = feedback?.mean_prediction_error_pct;

  if (predictions.length === 0 && outcomesCount === 0) {
    blockers.push("noPredictions");
    return finalize(10, reasons, warnings, blockers, "waitForSnapshots");
  }

  if (outcomesCount >= 20) reasons.push("adequateOutcomes");
  else if (outcomesCount >= 5) {
    warnings.push("limitedOutcomes");
    score -= 15;
  } else {
    blockers.push("tooFewOutcomes");
    score -= 30;
  }

  if (unresolved > 0) {
    warnings.push("unresolvedPredictions");
    score -= Math.min(20, unresolved);
  }

  if (stale) {
    warnings.push("staleOutcomes");
    score -= 25;
  }

  if (meanErr != null && Math.abs(meanErr) > 15) {
    warnings.push("highForecastError");
    score -= 15;
  } else if (meanErr != null && Math.abs(meanErr) <= 10) {
    reasons.push("acceptableForecastError");
  }

  const missingReturns = predictions.filter(
    (p) => p.outcome == null && !p.realized_return_pct
  ).length;
  if (missingReturns > predictions.length * 0.5 && predictions.length > 0) {
    warnings.push("missingRealizedReturns");
    score -= 10;
  }

  return finalize(score, reasons, warnings, blockers, stale ? "resolveOutcomes" : "monitorOutcomes", {
    stale,
  });
}

export function computePairsReliability(input: {
  result: PairsResearchResponse | null;
  running?: boolean;
}): ResearchReliabilityScore {
  const { result, running } = input;
  const reasons: string[] = [];
  const warnings: string[] = [];
  const blockers: string[] = [];

  if (running) {
    return finalize(40, ["loading"], [], [], "waitForRun", { researchOnly: true });
  }

  if (!result) {
    return finalize(
      15,
      [],
      [PBO_NOT_IMPLEMENTED_WARNING],
      ["noSavedRun"],
      "runPairsSearch",
      { researchOnly: true, forceStatus: "research_only" }
    );
  }

  let score = 65;
  const symbolCount = result.symbols_used?.length ?? 0;

  if (symbolCount >= 4) reasons.push("adequateUniverse");
  else {
    warnings.push("smallSymbolUniverse");
    score -= 15;
  }

  if (!result.statsmodels_available) {
    warnings.push("statsmodelsUnavailable");
    score -= 20;
  }

  if (result.cointegrated_count > 0) {
    reasons.push("cointegratedPairsFound");
    score += 10;
  } else {
    warnings.push("noCointegratedPairs");
    score -= 25;
  }

  if (result.observation_count < 120) {
    warnings.push("shortSampleLength");
    score -= 15;
  } else {
    reasons.push("adequateObservations");
  }

  if (result.insufficient_count > 0) {
    warnings.push("insufficientPairData");
    score -= 10;
  }

  warnings.push(PBO_NOT_IMPLEMENTED_WARNING);

  return finalize(score, reasons, warnings, blockers, "doNotApplyToScan", { researchOnly: true });
}

export function computeDataQualityReliability(input: {
  health: QuantHealthSummary | null;
  scheduler: SchedulerStatusResponse | null;
  failedJobCount?: number;
  loading?: boolean;
}): ResearchReliabilityScore {
  const { health, scheduler, failedJobCount = 0, loading } = input;
  const reasons: string[] = [];
  const warnings: string[] = [];
  const blockers: string[] = [];
  let score = 100;

  if (loading) {
    return finalize(50, ["loading"], [], [], "waitForLoad");
  }

  if (!health && !scheduler) {
    blockers.push("noHealthData");
    return finalize(20, reasons, warnings, blockers, "checkBackend");
  }

  if (health) {
    if (health.overall === "ok") reasons.push("quantHealthOk");
    else if (health.overall === "warning") {
      warnings.push("quantHealthWarning");
      score -= 15;
    } else {
      warnings.push("quantHealthError");
      score -= 30;
    }

    const staleSections = health.sections.filter((s) => s.severity === "warning" || s.severity === "error");
    for (const s of staleSections) {
      if (s.id.includes("scan") || s.message.toLowerCase().includes("scan")) warnings.push("staleScans");
      if (s.id.includes("ic") || s.message.toLowerCase().includes("ic")) warnings.push("staleIc");
      if (s.message.toLowerCase().includes("provider")) warnings.push("providerGap");
    }
  }

  if (scheduler) {
    if (scheduler.enabled) reasons.push("schedulerEnabled");
    else {
      warnings.push("schedulerDisabled");
      score -= 15;
    }
  } else {
    warnings.push("schedulerUnavailable");
    score -= 10;
  }

  if (failedJobCount > 0) {
    warnings.push("failedJobs");
    score -= Math.min(25, failedJobCount * 5);
  }

  return finalize(score, reasons, warnings, blockers, failedJobCount > 0 ? "reviewFailedJobs" : "monitorDataQuality");
}

export function computeModelAdminReliability(input: {
  version: V2VersionResponse | null;
  weights: { dynamic_enabled?: boolean } | null;
  audit: V2AuditResponse | null;
  factorsAdmin: V2FactorsAdminResponse | null;
  disabled?: boolean;
  panelErrors?: Record<string, string>;
  loading?: boolean;
}): ResearchReliabilityScore {
  const { version, weights, audit, factorsAdmin, disabled, panelErrors = {}, loading } = input;
  const reasons: string[] = [];
  const warnings: string[] = [];
  const blockers: string[] = [];
  let score = 100;

  if (disabled) {
    return finalize(0, [], [], ["featureDisabled"], "enableV2", { disabled: true });
  }
  if (loading) {
    return finalize(50, ["loading"], [], [], "waitForLoad");
  }

  if (!version && !weights && !audit && !factorsAdmin) {
    blockers.push("noAdminData");
    return finalize(15, reasons, warnings, blockers, "checkV2Endpoints");
  }

  if (version) reasons.push("versionLoaded");
  if (factorsAdmin?.factors?.length) reasons.push("factorCatalogLoaded");
  else {
    warnings.push("missingFactorCatalog");
    score -= 20;
  }

  if (weights?.dynamic_enabled) {
    warnings.push("dynamicWeightsEnabled");
    score -= 10;
  }

  if (audit?.events?.length) reasons.push("auditTrailPresent");
  else warnings.push("noAuditEvents");

  for (const key of Object.keys(panelErrors)) {
    warnings.push(`panelError:${key}`);
    score -= 10;
  }

  return finalize(score, reasons, warnings, blockers, "manualReviewBeforeChanges");
}

/** Map i18n keys for reasons/warnings/blockers/actions — resolved in UI. */
type ReliabilityMessageBuckets = {
  reasons?: Record<string, string>;
  warnings?: Record<string, string>;
  blockers?: Record<string, string>;
  actions?: Record<string, string>;
};

export function translateReliabilityList(
  keys: string[],
  section: "reasons" | "warnings" | "blockers" | "actions",
  t: { reliability: ReliabilityMessageBuckets }
): string[] {
  const bucket = t.reliability[section] ?? {};
  return keys.map((key) => {
    const [base, ...rest] = key.split(":");
    const detail = rest.join(":");
    const template = bucket[key] ?? bucket[base] ?? key;
    if (detail && template.includes("{count}")) {
      return template.replace("{count}", detail);
    }
    if (detail && template.includes("{detail}")) {
      return template.replace("{detail}", detail);
    }
    return template;
  });
}
