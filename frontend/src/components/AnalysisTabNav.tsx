"use client";

import clsx from "clsx";
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
  group: "core" | "research" | "workspace";
}

interface AnalysisTabNavProps {
  tabs: AnalysisTabConfig[];
  active: AnalysisTabId;
  onChange: (tab: AnalysisTabId) => void;
  ariaLabel: string;
}

export function AnalysisTabNav({ tabs, active, onChange, ariaLabel }: AnalysisTabNavProps) {
  const { t } = useTranslation();
  const activeTab = tabs.find((tab) => tab.id === active);
  const groupLabels: Record<AnalysisTabConfig["group"], string> = {
    core: t.analysis.tabGroupCore,
    research: t.analysis.tabGroupResearch,
    workspace: t.analysis.tabGroupWorkspace,
  };
  const groups = ["core", "research", "workspace"] as const;

  return (
    <div className="analysis-tab-nav">
      <nav className="analysis-tab-nav-scroll" aria-label={ariaLabel}>
        {groups.map((group) => {
          const groupTabs = tabs.filter((t) => t.group === group);
          if (groupTabs.length === 0) return null;
          return (
            <div key={group} className="analysis-tab-group" role="presentation">
              <span className="analysis-tab-group-label">{groupLabels[group]}</span>
              <div className="analysis-tab-group-items">
                {groupTabs.map((tab) => (
                  <button
                    key={tab.id}
                    type="button"
                    onClick={() => onChange(tab.id)}
                    aria-current={active === tab.id ? "page" : undefined}
                    className={clsx("analysis-tab-pill", active === tab.id && "analysis-tab-pill--active")}
                    title={tab.hint}
                  >
                    <span className="hidden sm:inline">{tab.label}</span>
                    <span className="sm:hidden">{tab.shortLabel}</span>
                  </button>
                ))}
              </div>
            </div>
          );
        })}
      </nav>
      {activeTab && (
        <p className="analysis-tab-hint" aria-live="polite">
          {activeTab.hint}
        </p>
      )}
    </div>
  );
}
