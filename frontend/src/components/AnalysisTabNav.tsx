"use client";

import clsx from "clsx";
import { useCallback, useEffect, useMemo, useRef } from "react";
import { useTranslation } from "@/lib/i18n";

export type AnalysisTabId =
  | "overview"
  | "score"
  | "risk"
  | "diagnostics"
  | "valuation"
  | "backtest"
  | "similar"
  | "report"
  | "notes";

export interface AnalysisTabConfig {
  id: AnalysisTabId;
  label: string;
  shortLabel: string;
  hint: string;
  group?: "core" | "research" | "workspace";
}

interface AnalysisTabNavProps {
  tabs: AnalysisTabConfig[];
  active: AnalysisTabId;
  onChange: (tab: AnalysisTabId) => void;
  ariaLabel: string;
}

const GROUP_ORDER: Array<"core" | "research" | "workspace"> = ["core", "research", "workspace"];

export function analysisPanelId(tab: AnalysisTabId): string {
  return `analysis-panel-${tab}`;
}

export function AnalysisTabNav({ tabs, active, onChange, ariaLabel }: AnalysisTabNavProps) {
  const { t } = useTranslation();
  const tabRefs = useRef<Map<AnalysisTabId, HTMLButtonElement>>(new Map());

  const groupLabels = useMemo(
    () => ({
      core: t.analysis.tabGroupCore,
      research: t.analysis.tabGroupResearch,
      workspace: t.analysis.tabGroupWorkspace,
    }),
    [t],
  );

  const grouped = useMemo(
    () =>
      GROUP_ORDER.map((group) => ({
        group,
        label: groupLabels[group],
        tabs: tabs.filter((tab) => (tab.group ?? "core") === group),
      })).filter((g) => g.tabs.length > 0),
    [tabs, groupLabels],
  );

  const flatTabs = useMemo(() => grouped.flatMap((g) => g.tabs), [grouped]);

  const onKeyDown = useCallback(
    (e: React.KeyboardEvent, index: number) => {
      if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
      e.preventDefault();
      const delta = e.key === "ArrowRight" ? 1 : -1;
      const next = flatTabs[(index + delta + flatTabs.length) % flatTabs.length];
      if (next) {
        onChange(next.id);
        tabRefs.current.get(next.id)?.focus();
      }
    },
    [flatTabs, onChange],
  );

  const tabIndexById = useMemo(() => {
    const map = new Map<AnalysisTabId, number>();
    flatTabs.forEach((tab, index) => map.set(tab.id, index));
    return map;
  }, [flatTabs]);

  useEffect(() => {
    tabRefs.current.get(active)?.scrollIntoView({ inline: "nearest", block: "nearest" });
  }, [active]);

  return (
    <nav className="analysis-tab-nav" aria-label={ariaLabel}>
      <div className="analysis-tab-nav-scroll" role="tablist">
        {grouped.map(({ group, label, tabs: groupTabs }, groupIndex) => (
          <div key={group} className="analysis-tab-group">
            {groupIndex > 0 && <span className="analysis-tab-group-sep" aria-hidden />}
            <span className="analysis-tab-group-label">{label}</span>
            <div className="analysis-tab-group-items analysis-tab-group-items--underline">
              {groupTabs.map((tab) => {
                const index = tabIndexById.get(tab.id) ?? 0;
                const isActive = active === tab.id;
                return (
                  <button
                    key={tab.id}
                    ref={(el) => {
                      if (el) tabRefs.current.set(tab.id, el);
                      else tabRefs.current.delete(tab.id);
                    }}
                    type="button"
                    role="tab"
                    id={`analysis-tab-${tab.id}`}
                    aria-selected={isActive}
                    aria-controls={analysisPanelId(tab.id)}
                    tabIndex={isActive ? 0 : -1}
                    onClick={() => onChange(tab.id)}
                    onKeyDown={(e) => onKeyDown(e, index)}
                    title={tab.hint}
                    className={clsx(
                      "analysis-tab-pill analysis-tab-pill--underline",
                      isActive && "analysis-tab-pill--active",
                    )}
                  >
                    <span className="analysis-tab-pill__label">{tab.label}</span>
                    {isActive && <span className="analysis-tab-pill__indicator" aria-hidden />}
                  </button>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </nav>
  );
}
