export const EXPERIMENT_STUDIO_STEPS = [
  "choose",
  "configure",
  "review",
  "run",
  "status",
  "result",
] as const;

export type ExperimentStudioStep = (typeof EXPERIMENT_STUDIO_STEPS)[number];

export const EXPERIMENT_TYPES = [
  "factor_validation",
  "walk_forward",
  "prediction_calibration",
  "pairs_discovery",
  "similar_signal",
  "portfolio_policy",
  "scan_evaluation",
] as const;

export type ExperimentType = (typeof EXPERIMENT_TYPES)[number];

export const UNIVERSE_SOURCES = [
  "latest_scan",
  "saved_scan",
  "watchlist",
  "portfolio_holdings",
  "full_bucket",
  "custom_symbols",
] as const;

export type UniverseSource = (typeof UNIVERSE_SOURCES)[number];

export const EXPERIMENT_PRESETS = [
  "quick_check",
  "standard_research",
  "robust_validation",
  "scan_eval_smoke",
  "custom",
] as const;

export type ExperimentPresetId = (typeof EXPERIMENT_PRESETS)[number];

export function isExperimentStudioStep(value: string | null): value is ExperimentStudioStep {
  return value != null && (EXPERIMENT_STUDIO_STEPS as readonly string[]).includes(value);
}

export function isExperimentType(value: string | null): value is ExperimentType {
  return value != null && (EXPERIMENT_TYPES as readonly string[]).includes(value);
}

export function resolveExperimentStudioRoute(searchParams: {
  get: (key: string) => string | null;
}): {
  step: ExperimentStudioStep;
  template: ExperimentType | null;
  experimentId: string | null;
  jobId: string | null;
  ideaId: string | null;
} {
  const stepParam = searchParams.get("step");
  const step: ExperimentStudioStep = isExperimentStudioStep(stepParam) ? stepParam : "choose";
  const templateParam = searchParams.get("template");
  const template = isExperimentType(templateParam) ? templateParam : null;
  return {
    step,
    template,
    experimentId: searchParams.get("experiment"),
    jobId: searchParams.get("job"),
    ideaId: searchParams.get("idea"),
  };
}

export function buildExperimentStudioHref(opts: {
  step?: ExperimentStudioStep;
  template?: ExperimentType | null;
  experimentId?: string | null;
  jobId?: string | null;
  ideaId?: string | null;
}): string {
  const params = new URLSearchParams();
  params.set("section", "experiments");
  params.set("step", opts.step ?? "choose");
  if (opts.template) params.set("template", opts.template);
  if (opts.experimentId) params.set("experiment", opts.experimentId);
  if (opts.jobId) params.set("job", opts.jobId);
  if (opts.ideaId) params.set("idea", opts.ideaId);
  return `/quant-lab?${params.toString()}`;
}

export function defaultWalkForwardDates(): { start_date: string; end_date: string } {
  const end = new Date();
  const start = new Date(end);
  start.setFullYear(start.getFullYear() - 1);
  return {
    start_date: start.toISOString().slice(0, 10),
    end_date: end.toISOString().slice(0, 10),
  };
}

export const SCAN_EVAL_ALGORITHM_VERSIONS = [
  "alphabetical_baseline",
  "stage_a_v1",
  "stage_a_v2",
  "scoring_engine_v1",
] as const;

export function defaultScanEvaluationParams(): Record<string, unknown> {
  const end = new Date();
  const start = new Date(end);
  start.setMonth(start.getMonth() - 2);
  return {
    ...defaultWalkForwardDates(),
    start_date: start.toISOString().slice(0, 10),
    end_date: end.toISOString().slice(0, 10),
    bucket: "penny",
    rebalance_frequency: "monthly",
    algorithm_versions: ["alphabetical_baseline", "stage_a_v2"],
    forward_horizons: [5, 20],
    stage_b_cap: 20,
    max_results: 10,
    max_universe: 25,
    spread_bps: 50,
    slippage_bps: 25,
    apply_penny_friction: true,
  };
}
