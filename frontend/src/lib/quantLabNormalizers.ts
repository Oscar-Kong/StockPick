import type {
  FactorPerformanceFactor,
  FactorPerformanceResponse,
  FeedbackSummaryResponse,
  PredictionSnapshotItem,
  PredictionsListResponse,
  SchedulerStatusResponse,
  V2AuditResponse,
  V2FactorsAdminResponse,
  WalkForwardResearchResponse,
  PairsResearchResponse,
} from "./types";

function isRecord(value: unknown): value is Record<string, unknown> {
  return value != null && typeof value === "object" && !Array.isArray(value);
}

function asNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function asString(value: unknown): string | null {
  return typeof value === "string" && value.length > 0 ? value : null;
}

export function normalizePredictionSnapshotItem(raw: unknown): PredictionSnapshotItem | null {
  if (!isRecord(raw)) return null;
  const id = asNumber(raw.id);
  const symbol = asString(raw.symbol);
  const sleeve = asString(raw.sleeve);
  const source = asString(raw.source);
  const createdAt = asString(raw.created_at) ?? asString(raw.as_of_date);
  if (id == null || !symbol || !sleeve || !source || !createdAt) return null;

  const outcomeRaw = raw.outcome;
  const outcome =
    outcomeRaw == null
      ? null
      : isRecord(outcomeRaw)
        ? {
            return_20d: asNumber(outcomeRaw.return_20d),
            return_60d: asNumber(outcomeRaw.return_60d),
            excess_vs_spy_60d: asNumber(outcomeRaw.excess_vs_spy_60d),
          }
        : null;

  return {
    id,
    symbol,
    sleeve,
    source,
    created_at: createdAt,
    price: asNumber(raw.price),
    recommendation: asString(raw.recommendation) ?? undefined,
    confidence: asNumber(raw.confidence),
    alpha_score: asNumber(raw.alpha_score),
    valuation_score: asNumber(raw.valuation_score),
    data_confidence: asNumber(raw.data_confidence),
    trade_id: asNumber(raw.trade_id) ?? undefined,
    outcome,
    score: asNumber(raw.score) ?? undefined,
    as_of_date: asString(raw.as_of_date) ?? undefined,
    resolved: typeof raw.resolved === "boolean" ? raw.resolved : undefined,
    realized_return_pct: asNumber(raw.realized_return_pct),
    forecast_error_pct: asNumber(raw.forecast_error_pct),
    resolved_at: asString(raw.resolved_at),
  };
}

export function normalizePredictionsListResponse(raw: unknown): PredictionsListResponse {
  if (!isRecord(raw)) return { predictions: [] };
  const list = Array.isArray(raw.predictions) ? raw.predictions : [];
  return {
    predictions: list
      .map(normalizePredictionSnapshotItem)
      .filter((item): item is PredictionSnapshotItem => item != null),
  };
}

export function normalizeFeedbackSummaryResponse(raw: unknown): FeedbackSummaryResponse {
  if (!isRecord(raw)) {
    return {
      outcomes_count: 0,
      snapshots_count: 0,
      recent_outcomes: [],
      recent_snapshots: [],
    };
  }
  const recentOutcomes = Array.isArray(raw.recent_outcomes) ? raw.recent_outcomes : [];
  const recentSnapshots = Array.isArray(raw.recent_snapshots) ? raw.recent_snapshots : [];
  return {
    outcomes_count: asNumber(raw.outcomes_count) ?? 0,
    snapshots_count: asNumber(raw.snapshots_count) ?? 0,
    mean_actual_return_pct: asNumber(raw.mean_actual_return_pct),
    mean_prediction_error_pct: asNumber(raw.mean_prediction_error_pct),
    recent_outcomes: recentOutcomes.filter(isRecord).map((o) => ({
      trade_id: asNumber(o.trade_id) ?? 0,
      actual_return_pct: asNumber(o.actual_return_pct),
      prediction_error_pct: asNumber(o.prediction_error_pct),
      closed_at: asString(o.closed_at),
    })),
    recent_snapshots: recentSnapshots
      .map(normalizePredictionSnapshotItem)
      .filter((item): item is PredictionSnapshotItem => item != null),
    stale: raw.stale === true,
  };
}

function normalizeFactorPerformanceFactor(raw: unknown): FactorPerformanceFactor | null {
  if (!isRecord(raw)) return null;
  const factorId = asString(raw.factor_id);
  if (!factorId) return null;
  const horizonsRaw = isRecord(raw.horizons) ? raw.horizons : {};
  const horizons: FactorPerformanceFactor["horizons"] = {};
  for (const [key, value] of Object.entries(horizonsRaw)) {
    if (!isRecord(value)) continue;
    const horizonDays = Number.parseInt(key, 10);
    horizons[key] = {
      factor_id: factorId,
      sleeve: asString(raw.sleeve) ?? "",
      horizon_days: Number.isFinite(horizonDays) ? horizonDays : 0,
      ic: asNumber(value.ic),
      ir: asNumber(value.ir),
      hit_rate: asNumber(value.hit_rate),
      sample_n: asNumber(value.sample_n) ?? 0,
      deciles: Array.isArray(value.deciles)
        ? (value.deciles as FactorPerformanceFactor["horizons"][string]["deciles"])
        : undefined,
    };
  }
  return {
    factor_id: factorId,
    sleeve: asString(raw.sleeve),
    horizons,
  };
}

export function normalizeFactorPerformanceResponse(raw: unknown): FactorPerformanceResponse {
  if (!isRecord(raw)) {
    return {
      as_of_date: null,
      horizons: [],
      factors: [],
      by_horizon: {},
      by_regime: {},
      by_sector: {},
    };
  }
  const factors = Array.isArray(raw.factors) ? raw.factors : [];
  return {
    as_of_date: asString(raw.as_of_date),
    horizons: Array.isArray(raw.horizons)
      ? raw.horizons.filter((h): h is number => typeof h === "number")
      : [],
    factors: factors
      .map(normalizeFactorPerformanceFactor)
      .filter((f): f is FactorPerformanceFactor => f != null),
    by_horizon: isRecord(raw.by_horizon) ? (raw.by_horizon as FactorPerformanceResponse["by_horizon"]) : {},
    by_regime: isRecord(raw.by_regime) ? (raw.by_regime as FactorPerformanceResponse["by_regime"]) : {},
    by_sector: isRecord(raw.by_sector) ? (raw.by_sector as FactorPerformanceResponse["by_sector"]) : {},
    market_regime:
      isRecord(raw.market_regime) && asString(raw.market_regime.regime) && asString(raw.market_regime.as_of_date)
        ? { regime: raw.market_regime.regime as string, as_of_date: raw.market_regime.as_of_date as string }
        : null,
    summary: isRecord(raw.summary) ? (raw.summary as FactorPerformanceResponse["summary"]) : undefined,
  };
}

export function normalizeSchedulerStatusResponse(raw: unknown): SchedulerStatusResponse {
  if (!isRecord(raw)) {
    return { enabled: false, recent_jobs: [] };
  }
  const jobs = Array.isArray(raw.recent_jobs) ? raw.recent_jobs : [];
  return {
    enabled: raw.enabled === true,
    quandl_configured: raw.quandl_configured === true,
    recent_jobs: jobs.filter(isRecord).map((j) => ({
      job_name: asString(j.job_name) ?? "unknown",
      status: asString(j.status) ?? "unknown",
      message: asString(j.message) ?? undefined,
      symbols_processed: asNumber(j.symbols_processed) ?? undefined,
    })),
  };
}

export function normalizeV2AuditResponse(raw: unknown): V2AuditResponse {
  if (!isRecord(raw)) return { events: [] };
  const events = Array.isArray(raw.events) ? raw.events : [];
  return {
    events: events.filter(isRecord).map((e) => ({
      id: asNumber(e.id) ?? undefined,
      event_type: asString(e.event_type) ?? undefined,
      symbol: asString(e.symbol),
      created_at: asString(e.created_at) ?? undefined,
      payload: isRecord(e.payload) ? e.payload : undefined,
    })),
  };
}

export function normalizeV2FactorsAdminResponse(raw: unknown): V2FactorsAdminResponse {
  if (!isRecord(raw)) {
    return { factors: [], trade_predictions_count: 0, trade_outcomes_count: 0 };
  }
  return {
    factors: Array.isArray(raw.factors) ? raw.factors : [],
    trade_predictions_count: asNumber(raw.trade_predictions_count) ?? 0,
    trade_outcomes_count: asNumber(raw.trade_outcomes_count) ?? 0,
    sleeve_filter: asString(raw.sleeve_filter),
    outcome_feedback_preview: raw.outcome_feedback_preview,
  };
}

export function normalizeWalkForwardResearchResponse(raw: unknown): WalkForwardResearchResponse {
  if (!isRecord(raw)) {
    return {
      run_id: "",
      status: "unknown",
      sleeve: "penny",
      start_date: "",
      end_date: "",
      rebalance_frequency: "monthly",
      forward_horizons: [],
      rebalance_periods: 0,
      periods_scored: 0,
      snapshots_written: 0,
    };
  }
  return {
    run_id: asString(raw.run_id) ?? "",
    status: asString(raw.status) ?? "unknown",
    sleeve: asString(raw.sleeve) ?? "penny",
    start_date: asString(raw.start_date) ?? "",
    end_date: asString(raw.end_date) ?? "",
    rebalance_frequency: asString(raw.rebalance_frequency) ?? "monthly",
    forward_horizons: Array.isArray(raw.forward_horizons)
      ? raw.forward_horizons.filter((h): h is number => typeof h === "number")
      : [],
    rebalance_periods: asNumber(raw.rebalance_periods) ?? 0,
    periods_scored: asNumber(raw.periods_scored) ?? 0,
    snapshots_written: asNumber(raw.snapshots_written) ?? 0,
    mean_turnover: asNumber(raw.mean_turnover),
    aggregate_horizons: isRecord(raw.aggregate_horizons) ? raw.aggregate_horizons : undefined,
    periods: Array.isArray(raw.periods) ? raw.periods : undefined,
    strategy_version: asString(raw.strategy_version) ?? undefined,
    factor_model_version: asString(raw.factor_model_version) ?? undefined,
    weights_updated: raw.weights_updated === true,
  };
}

export function normalizePairsResearchResponse(raw: unknown): PairsResearchResponse {
  if (!isRecord(raw)) {
    return {
      research_only: true,
      lookback_period: "1y",
      symbols_requested: [],
      symbols_used: [],
      excluded: [],
      observation_count: 0,
      pairs_evaluated: 0,
      pairs_returned: 0,
      cointegrated_count: 0,
      insufficient_count: 0,
      statsmodels_available: false,
      pairs: [],
      notes: [],
    };
  }
  const pairs = Array.isArray(raw.pairs) ? raw.pairs : [];
  return {
    research_only: raw.research_only !== false,
    lookback_period: asString(raw.lookback_period) ?? "1y",
    symbols_requested: Array.isArray(raw.symbols_requested)
      ? raw.symbols_requested.filter((s): s is string => typeof s === "string")
      : [],
    symbols_used: Array.isArray(raw.symbols_used)
      ? raw.symbols_used.filter((s): s is string => typeof s === "string")
      : [],
    excluded: Array.isArray(raw.excluded) ? raw.excluded.filter((s): s is string => typeof s === "string") : [],
    observation_count: asNumber(raw.observation_count) ?? 0,
    pairs_evaluated: asNumber(raw.pairs_evaluated) ?? 0,
    pairs_returned: asNumber(raw.pairs_returned) ?? 0,
    cointegrated_count: asNumber(raw.cointegrated_count) ?? 0,
    insufficient_count: asNumber(raw.insufficient_count) ?? 0,
    statsmodels_available: raw.statsmodels_available === true,
    pairs: pairs.filter(isRecord).map((p) => ({
      pair: Array.isArray(p.pair) ? (p.pair.filter((x): x is string => typeof x === "string") as string[]) : [],
      symbol_y: asString(p.symbol_y) ?? "",
      symbol_x: asString(p.symbol_x) ?? "",
      hedge_ratio: asNumber(p.hedge_ratio),
      intercept: asNumber(p.intercept),
      p_value: asNumber(p.p_value),
      cointegrated_5pct: p.cointegrated_5pct === true,
      half_life_sessions: asNumber(p.half_life_sessions),
      mean_reverting: typeof p.mean_reverting === "boolean" ? p.mean_reverting : null,
      latest_z_score: asNumber(p.latest_z_score),
      zscore_window: asNumber(p.zscore_window),
      spread_mean: asNumber(p.spread_mean),
      spread_std: asNumber(p.spread_std),
      observations: asNumber(p.observations) ?? undefined,
      sufficient: typeof p.sufficient === "boolean" ? p.sufficient : undefined,
      engine: asString(p.engine),
      warning: asString(p.warning),
    })),
    notes: Array.isArray(raw.notes) ? raw.notes.filter((n): n is string => typeof n === "string") : [],
  };
}

/** Factors with at least one horizon entry — safe for list rendering. */
export function factorPerformanceRows(data: FactorPerformanceResponse | null): FactorPerformanceFactor[] {
  if (!data?.factors?.length) return [];
  return data.factors.filter((f) => f.factor_id && Object.keys(f.horizons ?? {}).length > 0);
}

export function primaryFactorHorizon(factor: FactorPerformanceFactor) {
  const values = Object.values(factor.horizons ?? {});
  return values.length > 0 ? values[0] : null;
}
