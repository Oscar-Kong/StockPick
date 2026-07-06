import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { HypothesisReviewCard } from "./HypothesisReviewCard";
import { RuleTable } from "./RuleTable";
import { IntegrityBadge } from "./IntegrityBadge";

afterEach(() => cleanup());

describe("HypothesisReviewCard", () => {
  it("renders rationale and requires reason for approval", () => {
    render(
      <HypothesisReviewCard
        detail={{
          candidate_id: "hyp-1",
          session_id: "sess-1",
          state_version: 2,
          candidate_name: "Momentum tilt",
          economic_rationale: "Prices mean-revert slowly.",
          review_status: "PENDING_REVIEW",
          allowed_actions: { can_approve: true, can_reject: true },
        }}
        onRefresh={vi.fn()}
      />
    );

    expect(screen.getByText("Momentum tilt")).toBeInTheDocument();
    expect(screen.getByText(/Prices mean-revert slowly/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Approve for formula translation/i }));
    expect(screen.getByLabelText(/Reason \(required\)/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Approve hypothesis/i })).toBeDisabled();
  });
});

describe("RuleTable", () => {
  it("renders rule rows", () => {
    render(
      <RuleTable
        rows={[
          { category: "Signal", rule: "validation_rank_ic", actual: "0.04", required: "0.02", status: "PASS" },
        ]}
      />
    );
    expect(screen.getByText("validation_rank_ic")).toBeInTheDocument();
    expect(screen.getByText("PASS")).toBeInTheDocument();
  });
});

describe("IntegrityBadge", () => {
  it("labels failed integrity", () => {
    render(<IntegrityBadge status="FAILED" errorSummary="hash mismatch" />);
    expect(screen.getByRole("status")).toHaveTextContent("Integrity failed");
  });
});
