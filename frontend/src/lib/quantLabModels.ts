import type { QuantLabLegacyTab, QuantLabSection } from "@/lib/quantLabNavigation";

export const QUANT_LAB_MODEL_IDS = [
  "gbm",
  "hmm",
  "markowitz",
  "cointegration",
  "garch",
] as const;

export type QuantLabModelId = (typeof QUANT_LAB_MODEL_IDS)[number];

export type QuantLabModelStatus = "live" | "partial" | "reference";

export interface QuantLabModelEquation {
  id: string;
  tex: string;
}

export interface QuantLabModelLink {
  section: QuantLabSection;
  legacyTab?: QuantLabLegacyTab;
  href?: string;
}

export interface QuantLabModelDefinition {
  id: QuantLabModelId;
  status: QuantLabModelStatus;
  equations: QuantLabModelEquation[];
  link?: QuantLabModelLink;
}

/** Canonical model catalog — LaTeX is locale-neutral; copy lives in i18n. */
export const QUANT_LAB_MODEL_CATALOG: QuantLabModelDefinition[] = [
  {
    id: "gbm",
    status: "reference",
    equations: [
      {
        id: "sde",
        tex: "dS_t = \\mu S_t\\, dt + \\sigma S_t\\, dW_t",
      },
      {
        id: "solution",
        tex: "S_t = S_0 \\exp\\!\\left(\\left(\\mu - \\tfrac{\\sigma^2}{2}\\right)t + \\sigma W_t\\right)",
      },
      {
        id: "log_return",
        tex: "r_t = \\ln\\!\\left(\\frac{S_t}{S_{t-1}}\\right) \\sim \\mathcal{N}\\!\\left(\\mu - \\tfrac{\\sigma^2}{2},\\, \\sigma^2\\right)",
      },
      {
        id: "itô",
        tex: "d\\ln S_t = \\left(\\mu - \\tfrac{\\sigma^2}{2}\\right) dt + \\sigma\\, dW_t",
      },
    ],
  },
  {
    id: "hmm",
    status: "partial",
    equations: [
      {
        id: "transition",
        tex: "P(S_t = j \\mid S_{t-1} = i) = a_{ij}, \\quad \\sum_j a_{ij} = 1",
      },
      {
        id: "emission",
        tex: "P(O_t \\mid S_t = j) = b_j(O_t)",
      },
      {
        id: "joint",
        tex: "P(S_{1:T}, O_{1:T}) = \\pi_{S_1}\\, b_{S_1}(O_1) \\prod_{t=2}^{T} a_{S_{t-1}, S_t}\\, b_{S_t}(O_t)",
      },
      {
        id: "filter",
        tex: "\\alpha_t(j) = P(S_t = j, O_{1:t}) = b_j(O_t) \\sum_i \\alpha_{t-1}(i)\\, a_{ij}",
      },
    ],
    link: { section: "model-monitor" },
  },
  {
    id: "markowitz",
    status: "live",
    equations: [
      {
        id: "port_return",
        tex: "\\mu_p = \\mathbf{w}^{\\mathsf T}\\boldsymbol{\\mu}",
      },
      {
        id: "port_var",
        tex: "\\sigma_p^2 = \\mathbf{w}^{\\mathsf T}\\boldsymbol{\\Sigma}\\,\\mathbf{w}",
      },
      {
        id: "sharpe",
        tex: "\\max_{\\mathbf{w}}\\; \\frac{\\mathbf{w}^{\\mathsf T}\\boldsymbol{\\mu} - r_f}{\\sqrt{\\mathbf{w}^{\\mathsf T}\\boldsymbol{\\Sigma}\\,\\mathbf{w}}}",
      },
      {
        id: "constraints",
        tex: "\\sum_i w_i = 1 - c, \\quad 0 \\le w_i \\le w_{\\max}",
      },
      {
        id: "sample",
        tex: "\\hat{\\boldsymbol{\\mu}} = \\frac{252}{T}\\sum_{t=1}^{T}\\mathbf{r}_t, \\quad \\hat{\\boldsymbol{\\Sigma}} = \\frac{252}{T-1}\\sum_{t=1}^{T}(\\mathbf{r}_t - \\bar{\\mathbf{r}})(\\mathbf{r}_t - \\bar{\\mathbf{r}})^{\\mathsf T}",
      },
    ],
    link: { section: "legacy", href: "/?tab=research" },
  },
  {
    id: "cointegration",
    status: "live",
    equations: [
      {
        id: "regression",
        tex: "Y_t = \\alpha + \\beta X_t + \\varepsilon_t",
      },
      {
        id: "spread",
        tex: "s_t = Y_t - \\alpha - \\beta X_t",
      },
      {
        id: "eg",
        tex: "\\text{Engle–Granger: test } \\varepsilon_t \\text{ for unit root (ADF on OLS residuals)}",
      },
      {
        id: "zscore",
        tex: "z_t = \\frac{s_t - \\bar{s}_{t-w:t}}{\\hat{\\sigma}_{t-w:t}}",
      },
      {
        id: "halflife",
        tex: "\\Delta s_t = \\gamma\\, s_{t-1} + u_t, \\quad \\tau_{1/2} = -\\frac{\\ln 2}{\\gamma}\\; (\\gamma < 0)",
      },
    ],
    link: { section: "legacy", legacyTab: "pairs" },
  },
  {
    id: "garch",
    status: "partial",
    equations: [
      {
        id: "return",
        tex: "r_t = \\mu + \\varepsilon_t, \\quad \\varepsilon_t = \\sigma_t z_t, \\quad z_t \\sim \\mathcal{N}(0,1)",
      },
      {
        id: "garch11",
        tex: "\\sigma_t^2 = \\omega + \\alpha\\, \\varepsilon_{t-1}^2 + \\beta\\, \\sigma_{t-1}^2",
      },
      {
        id: "unconditional",
        tex: "\\mathbb{E}[\\sigma_t^2] = \\frac{\\omega}{1 - \\alpha - \\beta}\\; \\text{ when } \\alpha + \\beta < 1",
      },
      {
        id: "forecast",
        tex: "\\mathbb{E}_t[\\sigma_{t+h}^2] = \\omega \\sum_{i=0}^{h-1}(\\alpha + \\beta)^i + (\\alpha + \\beta)^h \\sigma_t^2",
      },
    ],
    link: { section: "model-monitor" },
  },
];

export function getQuantLabModel(id: QuantLabModelId): QuantLabModelDefinition | undefined {
  return QUANT_LAB_MODEL_CATALOG.find((m) => m.id === id);
}
