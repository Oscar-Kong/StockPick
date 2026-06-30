import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ModelsTab } from "./ModelsTab";

vi.mock("@/components/quant-lab/QuantEquation", () => ({
  QuantEquation: ({ tex }: { tex: string }) => <code data-testid="quant-equation">{tex}</code>,
}));

vi.mock("@/lib/i18n", () => ({
  useTranslation: () => ({
    t: {
      quantLab: {
        models: {
          title: "Quant model library",
          subtitle: "Core models with equations.",
          navAria: "Model library navigation",
          usageHeading: "In this project",
          equationsHeading: "Core equations",
          statusLive: "Live",
          statusPartial: "Partial",
          statusReference: "Reference",
          openRelated: "Open related tool →",
          gbm: {
            title: "Geometric Brownian Motion (GBM)",
            summary: "Log-normal price dynamics.",
            usage: "Empirical returns in backtests.",
            equations: { sde: "Price SDE", solution: "Solution", log_return: "Log return", itô: "Itô" },
          },
          hmm: {
            title: "Hidden Markov Model",
            summary: "Latent regimes.",
            usage: "Rule-based vol regime today.",
            equations: {
              transition: "Transition",
              emission: "Emission",
              joint: "Joint",
              filter: "Filter",
            },
          },
          markowitz: {
            title: "Markowitz Mean–Variance",
            summary: "Portfolio optimization.",
            usage: "Portfolio optimizer.",
            equations: {
              port_return: "Return",
              port_var: "Variance",
              sharpe: "Sharpe",
              constraints: "Constraints",
              sample: "Sample",
            },
          },
          cointegration: {
            title: "Cointegration",
            summary: "Pairs trading.",
            usage: "Pairs tab.",
            equations: {
              regression: "Regression",
              spread: "Spread",
              eg: "EG test",
              zscore: "Z-score",
              halflife: "Half-life",
            },
          },
          garch: {
            title: "GARCH",
            summary: "Vol clustering.",
            usage: "ATR regime proxy.",
            equations: {
              return: "Return",
              garch11: "GARCH(1,1)",
              unconditional: "Unconditional",
              forecast: "Forecast",
            },
          },
        },
      },
    },
    locale: "en",
  }),
}));

vi.mock("next/link", () => ({
  default: ({ href, children }: { href: string; children: React.ReactNode }) => (
    <a href={href}>{children}</a>
  ),
}));

describe("ModelsTab", () => {
  it("renders model library and switches models", () => {
    render(<ModelsTab />);
    expect(screen.getByRole("heading", { name: "Quant model library" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Geometric Brownian Motion (GBM)" })).toBeInTheDocument();
    expect(screen.getByText(/Price SDE/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Cointegration/i }));
    expect(screen.getByRole("heading", { name: "Cointegration" })).toBeInTheDocument();
    expect(screen.getByText(/Spread/)).toBeInTheDocument();
  });
});
