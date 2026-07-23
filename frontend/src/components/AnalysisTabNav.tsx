"use client";

import clsx from "clsx";
import { useCallback, useMemo, useRef } from "react";

export type AnalysisTabId =
  | "overview"
  | "drivers"
  | "risk"
  | "evidence"
  | "research"
  // Legacy ids kept for deep-links / migration
  | "score"
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
  /** @deprecated Visual groups removed — kept optional for callers during migration */
  group?: "core" | "research" | "workspace";
}

interface AnalysisTabNavProps {
  tabs: AnalysisTabConfig[];
  active: AnalysisTabId;
  onChange: (tab: AnalysisTabId) => void;
  ariaLabel: string;
}

const LEGACY_TAB_MAP: Partial<Record<AnalysisTabId, AnalysisTabId>> = {
  score: "drivers",
  valuation: "drivers",
  diagnostics: "evidence",
  backtest: "evidence",
  similar: "evidence",
  report: "research",
  notes: "research",
};

export function normalizeAnalysisTab(tab: AnalysisTabId): AnalysisTabId {
  return LEGACY_TAB_MAP[tab] ?? tab;
}

export function analysisPanelId(tab: AnalysisTabId): string {
  return `analysis-panel-${tab}`;
}

export function AnalysisTabNav({ tabs, active, onChange, ariaLabel }: AnalysisTabNavProps) {
  const tabRefs = useRef<Map<AnalysisTabId, HTMLButtonElement>>(new Map());
  const normalizedActive = normalizeAnalysisTab(active);

  const onKeyDown = useCallback(
    (e: React.KeyboardEvent, index: number) => {
      if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
      e.preventDefault();
      const delta = e.key === "ArrowRight" ? 1 : -1;
      const next = tabs[(index + delta + tabs.length) % tabs.length];
      if (next) {
        onChange(next.id);
        tabRefs.current.get(next.id)?.focus();
      }
    },
    [tabs, onChange],
  );

  const tabIndexById = useMemo(() => {
    const map = new Map<AnalysisTabId, number>();
    tabs.forEach((tab, index) => map.set(tab.id, index));
    return map;
  }, [tabs]);

  return (
    <nav className="analysis-tab-nav" aria-label={ariaLabel}>
      <div className="analysis-tab-nav-list" role="tablist">
        {tabs.map((tab) => {
          const index = tabIndexById.get(tab.id) ?? 0;
          const isActive = normalizedActive === tab.id;
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
              className={clsx("analysis-tab", isActive && "analysis-tab--active")}
            >
              {tab.label}
            </button>
          );
        })}
      </div>
    </nav>
  );
}
