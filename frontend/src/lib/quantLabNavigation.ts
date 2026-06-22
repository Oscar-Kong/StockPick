export const QUANT_LAB_SECTIONS = [
  "overview",
  "ideas",
  "experiments",
  "results",
  "model-monitor",
  "legacy",
] as const;

export type QuantLabSection = (typeof QUANT_LAB_SECTIONS)[number];

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

export function resolveQuantLabRoute(searchParams: {
  get: (key: string) => string | null;
}): { section: QuantLabSection; legacyTab: QuantLabLegacyTab } {
  const sectionParam = searchParams.get("section");
  const tabParam = searchParams.get("tab");

  if (!sectionParam && tabParam && isQuantLabLegacyTab(tabParam)) {
    return { section: "legacy", legacyTab: tabParam };
  }

  const section: QuantLabSection = isQuantLabSection(sectionParam) ? sectionParam : "overview";
  const legacyTab: QuantLabLegacyTab = isQuantLabLegacyTab(tabParam) ? tabParam : "factor-performance";
  return { section, legacyTab };
}

export function buildQuantLabHref(
  section: QuantLabSection,
  opts?: { legacyTab?: QuantLabLegacyTab; extra?: Record<string, string> }
): string {
  const params = new URLSearchParams();
  params.set("section", section);
  if (section === "legacy" && opts?.legacyTab) {
    params.set("tab", opts.legacyTab);
  }
  if (opts?.extra) {
    for (const [k, v] of Object.entries(opts.extra)) {
      params.set(k, v);
    }
  }
  return `/quant-lab?${params.toString()}`;
}

export const EXPERIMENT_LEGACY_LINKS: QuantLabLegacyTab[] = [
  "factor-performance",
  "walk-forward",
  "pairs",
];

export const RESULTS_LEGACY_LINKS: QuantLabLegacyTab[] = ["predictions", "walk-forward", "factor-performance"];

export const MONITOR_LEGACY_LINKS: QuantLabLegacyTab[] = [];
