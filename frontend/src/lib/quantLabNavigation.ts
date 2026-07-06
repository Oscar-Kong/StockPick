export const QUANT_LAB_SECTIONS = [
  "overview",
  "ideas",
  "experiments",
  "factor-discovery",
  "results",
  "model-monitor",
  "legacy",
] as const;

export type QuantLabSection = (typeof QUANT_LAB_SECTIONS)[number];

/** Primary research workflow — left-to-right in section nav. */
export const QUANT_LAB_WORKFLOW_SECTIONS = [
  "overview",
  "ideas",
  "experiments",
  "factor-discovery",
  "results",
  "model-monitor",
] as const satisfies readonly QuantLabSection[];

/** Sections tucked into the overflow menu on narrow viewports. */
export const QUANT_LAB_OVERFLOW_SECTIONS = ["legacy"] as const;

export type QuantLabPrimarySection = Exclude<QuantLabSection, "legacy">;

export const QUANT_LAB_SLEEVE_SECTIONS: readonly QuantLabPrimarySection[] = [
  "overview",
  "ideas",
  "experiments",
  "results",
  "model-monitor",
];

export const FACTOR_DISCOVERY_VIEWS = [
  "sessions",
  "new-research",
  "review-queue",
  "factors",
  "readiness",
  "promotion",
] as const;

export type FactorDiscoveryView = (typeof FACTOR_DISCOVERY_VIEWS)[number];

export const LEGACY_TABS = [
  "factor-performance",
  "walk-forward",
  "predictions",
  "pairs",
] as const;

export type QuantLabLegacyTab = (typeof LEGACY_TABS)[number];

export function isQuantLabSection(value: string | null): value is QuantLabSection {
  return value != null && (QUANT_LAB_SECTIONS as readonly string[]).includes(value);
}

export function isQuantLabLegacyTab(value: string | null): value is QuantLabLegacyTab {
  return value != null && (LEGACY_TABS as readonly string[]).includes(value);
}

export function isFactorDiscoveryView(value: string | null): value is FactorDiscoveryView {
  return value != null && (FACTOR_DISCOVERY_VIEWS as readonly string[]).includes(value);
}

export function resolveFactorDiscoveryView(searchParams: { get: (key: string) => string | null }): FactorDiscoveryView {
  const view = searchParams.get("fdView");
  return isFactorDiscoveryView(view) ? view : "sessions";
}

export function resolveQuantLabSection(sectionParam: string | null): QuantLabSection {
  if (sectionParam === "models") {
    return "model-monitor";
  }
  return isQuantLabSection(sectionParam) ? sectionParam : "overview";
}

export function resolveQuantLabRoute(searchParams: {
  get: (key: string) => string | null;
}): { section: QuantLabSection; legacyTab: QuantLabLegacyTab } {
  const sectionParam = searchParams.get("section");
  const tabParam = searchParams.get("tab");

  if (!sectionParam && tabParam && isQuantLabLegacyTab(tabParam)) {
    return { section: "legacy", legacyTab: tabParam };
  }

  const section = resolveQuantLabSection(sectionParam);
  const legacyTab: QuantLabLegacyTab = isQuantLabLegacyTab(tabParam) ? tabParam : "factor-performance";
  return { section, legacyTab };
}

export function buildQuantLabHref(
  section: QuantLabSection,
  opts?: { legacyTab?: QuantLabLegacyTab; fdView?: FactorDiscoveryView; extra?: Record<string, string> }
): string {
  const params = new URLSearchParams();
  params.set("section", section);
  if (section === "legacy" && opts?.legacyTab) {
    params.set("tab", opts.legacyTab);
  }
  if (section === "factor-discovery" && opts?.fdView) {
    params.set("fdView", opts.fdView);
  }
  if (opts?.extra) {
    for (const [k, v] of Object.entries(opts.extra)) {
      params.set(k, v);
    }
  }
  return `/quant-lab?${params.toString()}`;
}

export function buildFactorDiscoveryHref(
  view: FactorDiscoveryView,
  extra?: Record<string, string>
): string {
  return buildQuantLabHref("factor-discovery", { fdView: view, extra });
}

export const EXPERIMENT_LEGACY_LINKS: QuantLabLegacyTab[] = [
  "factor-performance",
  "walk-forward",
  "pairs",
];

export const RESULTS_LEGACY_LINKS: QuantLabLegacyTab[] = ["predictions", "walk-forward", "factor-performance"];

export const MONITOR_LEGACY_LINKS: QuantLabLegacyTab[] = [];
