"use client";

import clsx from "clsx";
import { useCallback, useEffect, useRef } from "react";

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

export function AnalysisTabNav({ tabs, active, onChange, ariaLabel }: AnalysisTabNavProps) {
  const tabRefs = useRef<Map<AnalysisTabId, HTMLButtonElement>>(new Map());

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
    [onChange, tabs]
  );

  useEffect(() => {
    tabRefs.current.get(active)?.scrollIntoView({ inline: "nearest", block: "nearest" });
  }, [active]);

  return (
    <nav className="analysis-tab-strip" aria-label={ariaLabel}>
      {tabs.map((tab, index) => {
        const isWorkspaceTab = tab.id === "report" || tab.id === "notes";
        const prevTab = tabs[index - 1];
        const showDivider =
          isWorkspaceTab && prevTab && prevTab.id !== "report" && prevTab.id !== "notes" && tab.id === "report";

        return (
          <span key={tab.id} className="analysis-tab-strip__item">
            {showDivider && <span className="analysis-tab-strip__divider" aria-hidden />}
            <button
              ref={(el) => {
                if (el) tabRefs.current.set(tab.id, el);
                else tabRefs.current.delete(tab.id);
              }}
              type="button"
              role="tab"
              aria-selected={active === tab.id}
              aria-current={active === tab.id ? "page" : undefined}
              tabIndex={active === tab.id ? 0 : -1}
              onClick={() => onChange(tab.id)}
              onKeyDown={(e) => onKeyDown(e, index)}
              title={tab.hint}
              className={clsx("analysis-tab-strip__tab", active === tab.id && "analysis-tab-strip__tab--active")}
            >
              {tab.label}
            </button>
          </span>
        );
      })}
    </nav>
  );
}
