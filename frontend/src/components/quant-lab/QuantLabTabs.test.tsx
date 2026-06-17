import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, cleanup } from "@testing-library/react";
import { en } from "@/lib/i18n/messages/en";
import { FactorPerformanceTab } from "./FactorPerformanceTab";
import { WalkForwardTab } from "./WalkForwardTab";
import { PredictionsTab } from "./PredictionsTab";
import { PairsTab } from "./PairsTab";
import { DataQualityTab } from "./DataQualityTab";
import { ModelAdminTab } from "./ModelAdminTab";
import * as api from "@/lib/api";

vi.mock("@/lib/i18n", () => ({
  useTranslation: () => ({ t: en, locale: "en" }),
  useTRef: () => ({ current: en }),
}));

vi.mock("@/components/quant/QuantHealthCard", () => ({
  QuantHealthCard: () => <div data-testid="quant-health-card">Quant Health</div>,
}));

vi.mock("@/lib/api", () => ({
  getV2FactorPerformance: vi.fn(),
  getV2Predictions: vi.fn(),
  getV2FeedbackSummary: vi.fn(),
  runWalkForwardResearch: vi.fn(),
  getWalkForwardLatest: vi.fn(),
  getWalkForwardRun: vi.fn(),
  runPairsResearch: vi.fn(),
  getQuantLabEvidence: vi.fn(),
  getV2Version: vi.fn(),
  getV2SleeveWeights: vi.fn(),
  getV2Audit: vi.fn(),
  getV2FactorsAdmin: vi.fn(),
  getSchedulerStatus: vi.fn(),
  getQuantHealthSummary: vi.fn(),
  getHealth: vi.fn(),
  getSavedProgressSummary: vi.fn(),
  getLatestScan: vi.fn(),
}));

const mocked = vi.mocked(api);

const emptyFeedbackSummary = {
  outcomes_count: 0,
  snapshots_count: 0,
  mean_prediction_error_pct: null,
  recent_outcomes: [],
  recent_snapshots: [],
} satisfies Awaited<ReturnType<typeof api.getV2FeedbackSummary>>;

describe("Quant Lab tabs", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocked.getQuantHealthSummary.mockResolvedValue({
      overall: "ok",
      checked_at: new Date().toISOString(),
      sections: [],
    });
    mocked.getWalkForwardLatest.mockResolvedValue({
      id: "walk_forward",
      available: false,
      reason: "No saved run found",
      stale: false,
      warnings: [],
      trust_indicator: "no_saved_run",
      research_only: true,
    });
    mocked.getWalkForwardRun.mockResolvedValue({ run_id: "x", run_type: "walk_forward_research" });
  });

  afterEach(() => {
    cleanup();
  });

  const expectReliabilityCard = () => {
    expect(screen.getByTestId("research-reliability-card")).toBeInTheDocument();
  };

  describe("FactorPerformanceTab", () => {
    it("renders tab title", async () => {
      mocked.getV2FactorPerformance.mockResolvedValue({
        as_of_date: null,
        horizons: [],
        factors: [],
        by_horizon: {},
        by_regime: {},
        by_sector: {},
      });
      render(<FactorPerformanceTab />);
      expectReliabilityCard();
      expect(screen.getByText(en.quantLab.tabFactorPerformance)).toBeInTheDocument();
      await waitFor(() => {
        expect(screen.getByText(en.quantLab.noFactorIc)).toBeInTheDocument();
      });
    });

    it("shows empty IC state after load", async () => {
      mocked.getV2FactorPerformance.mockResolvedValue({
        as_of_date: null,
        horizons: [],
        factors: [],
        by_horizon: {},
        by_regime: {},
        by_sector: {},
      });
      render(<FactorPerformanceTab />);
      await waitFor(() => {
        expect(screen.getByText(en.quantLab.noFactorIc)).toBeInTheDocument();
      });
      expect(mocked.getV2FactorPerformance).toHaveBeenCalled();
    });

    it("shows insufficient_data reliability when IC empty", async () => {
      mocked.getV2FactorPerformance.mockResolvedValue({
        as_of_date: null,
        horizons: [],
        factors: [],
        by_horizon: {},
        by_regime: {},
        by_sector: {},
      });
      render(<FactorPerformanceTab />);
      await waitFor(() => {
        expect(screen.getByText(en.reliability.statusInsufficientData)).toBeInTheDocument();
      });
    });

    it("shows disabled reliability when feature off", async () => {
      mocked.getV2FactorPerformance.mockRejectedValue(
        new Error('{"detail":"SCORE_ENGINE_V2_ENABLED is false"}')
      );
      render(<FactorPerformanceTab />);
      await waitFor(() => {
        expect(screen.getByText(en.reliability.statusDisabled)).toBeInTheDocument();
      });
    });

    it("shows feature disabled on 503", async () => {
      mocked.getV2FactorPerformance.mockRejectedValue(
        new Error('{"detail":"SCORE_ENGINE_V2_ENABLED is false"}')
      );
      render(<FactorPerformanceTab />);
      await waitFor(() => {
        expect(screen.getByText(en.quantLab.featureDisabled)).toBeInTheDocument();
      });
    });

    it("shows error state with retry on API failure", async () => {
      mocked.getV2FactorPerformance.mockRejectedValue(new Error("network down"));
      render(<FactorPerformanceTab />);
      await waitFor(() => {
        expect(screen.getByText("network down")).toBeInTheDocument();
      });
    });

    it("handles malformed response without crashing", async () => {
      mocked.getV2FactorPerformance.mockResolvedValue({
        as_of_date: "2020-01-01",
        horizons: null as unknown as [],
        factors: [{ factor_id: null, horizons: null } as never],
        by_horizon: {},
        by_regime: {},
        by_sector: {},
      });
      render(<FactorPerformanceTab />);
      await waitFor(() => {
        expect(screen.getByText(en.quantLab.noFactorIc)).toBeInTheDocument();
      });
    });
  });

  describe("WalkForwardTab", () => {
    it("renders research-only warning and reliability card", () => {
      render(<WalkForwardTab />);
      expectReliabilityCard();
      expect(screen.getByText(en.quantLab.researchOnlyExtended)).toBeInTheDocument();
      expect(screen.getByText(en.product.researchOnlyBadge)).toBeInTheDocument();
    });

    it("does not POST walk-forward until run clicked", async () => {
      render(<WalkForwardTab />);
      await waitFor(() => {
        expect(mocked.getWalkForwardLatest).toHaveBeenCalled();
      });
      expect(mocked.runWalkForwardResearch).not.toHaveBeenCalled();
      expect(screen.getByText(en.quantLab.walkForwardNoRunYet)).toBeInTheDocument();
    });

    it("calls API only after run clicked", async () => {
      mocked.runWalkForwardResearch.mockResolvedValue({
        run_id: "abc",
        status: "completed",
        sleeve: "medium",
        start_date: "2024-01-01",
        end_date: "2026-01-01",
        rebalance_frequency: "monthly",
        forward_horizons: [20],
        rebalance_periods: 0,
        periods_scored: 0,
        snapshots_written: 0,
      });
      render(<WalkForwardTab />);
      fireEvent.click(screen.getByRole("button", { name: en.quantLab.runWalkForward }));
      await waitFor(() => {
        expect(mocked.runWalkForwardResearch).toHaveBeenCalledTimes(1);
      });
    });

    it("validates horizons before API call", async () => {
      render(<WalkForwardTab />);
      fireEvent.click(screen.getByLabelText("20d"));
      fireEvent.click(screen.getByLabelText("60d"));
      fireEvent.click(screen.getByRole("button", { name: en.quantLab.runWalkForward }));
      expect(screen.getByText(en.quantLab.walkForwardNoHorizons)).toBeInTheDocument();
      expect(mocked.runWalkForwardResearch).not.toHaveBeenCalled();
    });

    it("shows empty periods state when periods_scored is 0", async () => {
      mocked.runWalkForwardResearch.mockResolvedValue({
        run_id: "abc",
        status: "completed",
        sleeve: "medium",
        start_date: "2024-01-01",
        end_date: "2026-01-01",
        rebalance_frequency: "monthly",
        forward_horizons: [20],
        rebalance_periods: 0,
        periods_scored: 0,
        snapshots_written: 0,
      });
      render(<WalkForwardTab />);
      fireEvent.click(screen.getByRole("button", { name: en.quantLab.runWalkForward }));
      await waitFor(() => {
        expect(screen.getByText(en.quantLab.walkForwardNoPeriods)).toBeInTheDocument();
      });
    });
    it("shows weak walk-forward overfitting warnings after run", async () => {
      mocked.runWalkForwardResearch.mockResolvedValue({
        run_id: "abc",
        status: "completed",
        sleeve: "medium",
        start_date: "2024-01-01",
        end_date: "2026-01-01",
        rebalance_frequency: "monthly",
        forward_horizons: [20],
        rebalance_periods: 1,
        periods_scored: 1,
        snapshots_written: 0,
      });
      render(<WalkForwardTab />);
      fireEvent.click(screen.getByRole("button", { name: en.quantLab.runWalkForward }));
      await waitFor(() => {
        const panel = screen.getByTestId("walk-forward-overfitting-warnings");
        expect(panel).toBeInTheDocument();
        expect(panel.textContent).toContain(en.reliability.warnings.noTransactionCosts);
      });
    });

    it("does not expose auto-apply button", () => {
      render(<WalkForwardTab />);
      expect(screen.queryByRole("button", { name: /apply/i })).not.toBeInTheDocument();
    });
  });

  describe("PredictionsTab", () => {
    it("renders tab title and reliability card", async () => {
      mocked.getV2Predictions.mockResolvedValue({ predictions: [] });
      mocked.getV2FeedbackSummary.mockResolvedValue(emptyFeedbackSummary);
      render(<PredictionsTab />);
      expectReliabilityCard();
      expect(screen.getByText(en.quantLab.tabPredictions)).toBeInTheDocument();
      await waitFor(() => {
        expect(screen.getByText(en.home.unresolvedPredictions)).toBeInTheDocument();
      });
    });

    it("handles partial feedback failure independently", async () => {
      mocked.getV2Predictions.mockResolvedValue({ predictions: [] });
      mocked.getV2FeedbackSummary.mockRejectedValue(new Error("feedback down"));
      render(<PredictionsTab />);
      await waitFor(() => {
        expect(screen.getByText("feedback down")).toBeInTheDocument();
      });
      expect(screen.getByText(en.home.unresolvedPredictions)).toBeInTheDocument();
    });

    it("shows feature disabled when predictions endpoint returns 503", async () => {
      mocked.getV2Predictions.mockRejectedValue(
        new Error('{"detail":"SCORE_ENGINE_V2_ENABLED is false"}')
      );
      mocked.getV2FeedbackSummary.mockResolvedValue(emptyFeedbackSummary);
      render(<PredictionsTab />);
      await waitFor(() => {
        expect(screen.getByText(en.quantLab.predictionsDisabled)).toBeInTheDocument();
      });
    });

    it("handles malformed prediction rows without crashing", async () => {
      mocked.getV2Predictions.mockResolvedValue({
        predictions: [{ symbol: "AAPL", alpha_score: null, recommendation: null } as never],
      });
      mocked.getV2FeedbackSummary.mockResolvedValue({
        ...emptyFeedbackSummary,
        outcomes_count: 0,
      });
      render(<PredictionsTab />);
      await waitFor(() => {
        expect(screen.getByText("AAPL")).toBeInTheDocument();
      });
    });
  });

  describe("PairsTab", () => {
    it("renders research-only warning, badge, and reliability card", () => {
      render(<PairsTab />);
      expectReliabilityCard();
      expect(screen.getByText(en.quantLab.researchOnlyExtended)).toBeInTheDocument();
      expect(screen.getAllByText(en.product.researchOnlyBadge).length).toBeGreaterThanOrEqual(1);
    });

    it("does not call API on mount", () => {
      render(<PairsTab />);
      expect(mocked.runPairsResearch).not.toHaveBeenCalled();
      expect(screen.getByText(en.quantLab.pairsNoRunYet)).toBeInTheDocument();
    });

    it("validates min symbols without API call", async () => {
      render(<PairsTab />);
      fireEvent.change(screen.getByRole("textbox"), { target: { value: "AAPL" } });
      fireEvent.click(screen.getByRole("button", { name: en.quantLab.runPairs }));
      expect(screen.getByText(en.quantLab.pairsMinSymbols)).toBeInTheDocument();
      expect(mocked.runPairsResearch).not.toHaveBeenCalled();
    });

    it("calls API after valid input", async () => {
      mocked.runPairsResearch.mockResolvedValue({
        research_only: true,
        lookback_period: "1y",
        symbols_requested: ["AAPL", "MSFT"],
        symbols_used: ["AAPL", "MSFT"],
        excluded: [],
        observation_count: 100,
        pairs_evaluated: 1,
        pairs_returned: 1,
        cointegrated_count: 0,
        insufficient_count: 1,
        statsmodels_available: false,
        pairs: [],
        notes: [],
      });
      render(<PairsTab />);
      fireEvent.click(screen.getByRole("button", { name: en.quantLab.runPairs }));
      await waitFor(() => {
        expect(mocked.runPairsResearch).toHaveBeenCalledTimes(1);
      });
    });

    it("handles statsmodels unavailable without crashing", async () => {
      mocked.runPairsResearch.mockResolvedValue({
        research_only: true,
        lookback_period: "1y",
        symbols_requested: ["AAPL", "MSFT"],
        symbols_used: ["AAPL", "MSFT"],
        excluded: [],
        observation_count: 100,
        pairs_evaluated: 1,
        pairs_returned: 0,
        cointegrated_count: 0,
        insufficient_count: 1,
        statsmodels_available: false,
        pairs: [],
        notes: ["statsmodels not installed"],
      });
      render(<PairsTab />);
      fireEvent.click(screen.getByRole("button", { name: en.quantLab.runPairs }));
      await waitFor(() => {
        expect(screen.getAllByText(/statsmodels not installed/).length).toBeGreaterThan(0);
      });
    });
  });

  describe("DataQualityTab", () => {
    it("renders quant health card, scheduler panel, and reliability card", async () => {
      mocked.getSchedulerStatus.mockResolvedValue({
        enabled: true,
        recent_jobs: [],
      });
      render(<DataQualityTab />);
      expectReliabilityCard();
      expect(screen.getByText(en.quantLab.tabDataQuality)).toBeInTheDocument();
      expect(screen.getByTestId("quant-health-card")).toBeInTheDocument();
      await waitFor(() => {
        expect(screen.getByText(en.quantLab.noSchedulerJobs)).toBeInTheDocument();
      });
    });

    it("shows scheduler warning when unavailable", async () => {
      mocked.getSchedulerStatus.mockRejectedValue(new Error("scheduler offline"));
      render(<DataQualityTab />);
      await waitFor(() => {
        expect(screen.getByText(en.settings.schedulerUnavailable)).toBeInTheDocument();
      });
    });
  });

  describe("ModelAdminTab", () => {
    it("renders version and reliability card when loaded", async () => {
      mocked.getV2Version.mockResolvedValue({
        strategy_version: "v1",
        factor_model_version: "quant-v2",
      });
      mocked.getV2SleeveWeights.mockResolvedValue({
        sleeve: "medium",
        regime: "neutral",
        dynamic_enabled: false,
        weights: {},
      });
      mocked.getV2Audit.mockResolvedValue({ events: [] });
      mocked.getV2FactorsAdmin.mockResolvedValue({
        factors: [],
        trade_predictions_count: 0,
        trade_outcomes_count: 0,
      });
      render(<ModelAdminTab />);
      await waitFor(() => {
        expectReliabilityCard();
        expect(screen.getByText(/strategy: v1/)).toBeInTheDocument();
      });
    });

    it("shows feature disabled when v2 is off", async () => {
      mocked.getV2Version.mockRejectedValue(
        new Error('{"detail":"SCORE_ENGINE_V2_ENABLED is false"}')
      );
      mocked.getV2SleeveWeights.mockRejectedValue(
        new Error('{"detail":"SCORE_ENGINE_V2_ENABLED is false"}')
      );
      mocked.getV2Audit.mockRejectedValue(new Error('{"detail":"SCORE_ENGINE_V2_ENABLED is false"}'));
      mocked.getV2FactorsAdmin.mockRejectedValue(
        new Error('{"detail":"SCORE_ENGINE_V2_ENABLED is false"}')
      );
      render(<ModelAdminTab />);
      await waitFor(() => {
        expect(screen.getByText(en.quantLab.featureDisabled)).toBeInTheDocument();
      });
    });

    it("renders partial panels when one endpoint fails", async () => {
      mocked.getV2Version.mockResolvedValue({
        strategy_version: "v1",
        factor_model_version: "quant-v2",
      });
      mocked.getV2SleeveWeights.mockRejectedValue(new Error("weights failed"));
      mocked.getV2Audit.mockResolvedValue({ events: [] });
      mocked.getV2FactorsAdmin.mockResolvedValue({
        factors: [],
        trade_predictions_count: 0,
        trade_outcomes_count: 0,
      });
      render(<ModelAdminTab />);
      await waitFor(() => {
        expect(screen.getByText(/strategy: v1/)).toBeInTheDocument();
        expect(screen.getByText("weights failed")).toBeInTheDocument();
      });
    });
  });
});
