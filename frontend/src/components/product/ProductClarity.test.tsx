import { describe, expect, it, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { en } from "@/lib/i18n/messages/en";
import { ScanScoringNote } from "./ScanScoringNote";
import { QuantLabScanRelationshipPanel } from "./QuantLabScanRelationshipPanel";
import { ApplyChangesConfirm, ApplyChangesNotice } from "./ApplyChangesNotice";

vi.mock("@/lib/i18n", () => ({
  useTranslation: () => ({ t: en, locale: "en" }),
}));

describe("ScanScoringNote", () => {
  afterEach(() => cleanup());

  it("shows score source and Quant Lab link", () => {
    render(
      <ScanScoringNote
        scoringEngineUsed={true}
        paritySummary={{ average_delta: 1.2, max_delta: 3.4, recommendation_bucket_diffs: 0 }}
        lastScanAt="2026-06-01T12:00:00Z"
        scanStale={false}
      />
    );
    expect(screen.getByText(en.product.scanScoredTitle)).toBeInTheDocument();
    expect(screen.getByText(en.analysis.scoreSourceV2)).toBeInTheDocument();
    expect(screen.getByText(en.product.parityAvailable)).toBeInTheDocument();
    expect(screen.getByText(en.product.dataFresh)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: en.product.openQuantLabValidation })).toHaveAttribute(
      "href",
      "/quant-lab"
    );
  });

  it("shows parity unavailable when no summary", () => {
    render(
      <ScanScoringNote scoringEngineUsed={false} paritySummary={null} lastScanAt={null} />
    );
    expect(screen.getByText(en.analysis.scoreSourceLegacy)).toBeInTheDocument();
    expect(screen.getByText(en.product.parityUnavailable)).toBeInTheDocument();
  });
});

describe("QuantLabScanRelationshipPanel", () => {
  afterEach(() => cleanup());

  it("shows how Quant Lab affects Scan copy", () => {
    render(<QuantLabScanRelationshipPanel />);
    expect(screen.getByText(en.product.quantLabAffectsScanTitle)).toBeInTheDocument();
    expect(screen.getByText(en.product.quantLabAffectsScanCopy)).toBeInTheDocument();
    expect(screen.getByText(en.product.flowProduction)).toBeInTheDocument();
  });
});

describe("ApplyChangesNotice", () => {
  afterEach(() => cleanup());

  it("shows manual review when no apply action", () => {
    render(<ApplyChangesNotice />);
    expect(screen.getByText(en.product.manualReviewRequired)).toBeInTheDocument();
  });

  it("ApplyChangesConfirm requires confirmation", () => {
    const onConfirm = vi.fn();
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(false);
    render(<ApplyChangesConfirm label="Apply weights" onConfirm={onConfirm} />);
    fireEvent.click(screen.getByRole("button", { name: "Apply weights" }));
    expect(confirmSpy).toHaveBeenCalled();
    expect(onConfirm).not.toHaveBeenCalled();
    confirmSpy.mockRestore();
  });

  it("ApplyChangesConfirm calls handler when confirmed", () => {
    const onConfirm = vi.fn();
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
    render(<ApplyChangesConfirm label="Apply weights" onConfirm={onConfirm} />);
    fireEvent.click(screen.getByRole("button", { name: "Apply weights" }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
    confirmSpy.mockRestore();
  });
});
