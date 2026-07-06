"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

export type PortfolioTab = "today" | "plan" | "research" | "activity";

export type ResearchPanel = "optimize" | "backtest" | "exposure" | "allocation";

const TABS: PortfolioTab[] = ["today", "plan", "activity", "research"];
const RESEARCH_PANELS: ResearchPanel[] = ["optimize", "backtest", "exposure", "allocation"];

export function parsePortfolioTab(raw: string | null): PortfolioTab {
  if (raw === "plan" || raw === "research" || raw === "activity") return raw;
  return "today";
}

export function parseResearchPanel(raw: string | null): ResearchPanel | null {
  if (!raw) return null;
  const legacy: Record<string, ResearchPanel> = {
    rebalance: "optimize",
    risk: "exposure",
    backtest: "backtest",
    advanced: "allocation",
  };
  if (raw in legacy) return legacy[raw];
  return RESEARCH_PANELS.includes(raw as ResearchPanel) ? (raw as ResearchPanel) : null;
}

export function usePortfolioTab() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [tab, setTabState] = useState<PortfolioTab>(() =>
    parsePortfolioTab(searchParams.get("tab"))
  );
  const [researchPanel, setResearchPanelState] = useState<ResearchPanel>(() => {
    const fromPanel = parseResearchPanel(searchParams.get("panel"));
    if (fromPanel) return fromPanel;
    const fromTools = parseResearchPanel(searchParams.get("tools"));
    return fromTools ?? "optimize";
  });

  useEffect(() => {
    const nextTab = parsePortfolioTab(searchParams.get("tab"));
    setTabState(nextTab);
    const panel =
      parseResearchPanel(searchParams.get("panel")) ??
      parseResearchPanel(searchParams.get("tools"));
    if (panel) setResearchPanelState(panel);
  }, [searchParams]);

  const setTab = useCallback(
    (next: PortfolioTab, panel?: ResearchPanel) => {
      const params = new URLSearchParams(searchParams.toString());
      if (next === "today") {
        params.delete("tab");
        params.delete("panel");
        params.delete("tools");
      } else {
        params.set("tab", next);
        if (next === "research") {
          const rp = panel ?? researchPanel;
          params.set("panel", rp);
          params.delete("tools");
        } else {
          params.delete("panel");
          params.delete("tools");
        }
      }
      params.delete("journal");
      const qs = params.toString();
      router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
      setTabState(next);
      if (panel) setResearchPanelState(panel);
    },
    [pathname, researchPanel, router, searchParams]
  );

  const setResearchPanel = useCallback(
    (panel: ResearchPanel) => {
      const params = new URLSearchParams(searchParams.toString());
      params.set("tab", "research");
      params.set("panel", panel);
      params.delete("tools");
      const qs = params.toString();
      router.replace(`${pathname}?${qs}`, { scroll: false });
      setTabState("research");
      setResearchPanelState(panel);
    },
    [pathname, router, searchParams]
  );

  const legacyJournal = searchParams.get("journal") === "1";
  const legacyHash =
    typeof window !== "undefined" &&
    (window.location.hash === "#home-journal" || window.location.hash === "#portfolio-tools");

  const initialTabHint = useMemo(() => {
    if (legacyJournal || (typeof window !== "undefined" && window.location.hash === "#home-journal")) {
      return "activity" as const;
    }
    if (
      searchParams.get("tools") ||
      (typeof window !== "undefined" && window.location.hash === "#portfolio-tools")
    ) {
      return "research" as const;
    }
    return null;
  }, [legacyJournal, searchParams]);

  return {
    tab,
    researchPanel,
    setTab,
    setResearchPanel,
    initialTabHint,
    legacyHash,
    tabs: TABS,
    researchPanels: RESEARCH_PANELS,
  };
}
