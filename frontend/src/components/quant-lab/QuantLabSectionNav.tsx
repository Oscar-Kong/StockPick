"use client";

import { AppTabBar, AppTabButton } from "@/components/AppTabs";
import {
  QUANT_LAB_OVERFLOW_SECTIONS,
  QUANT_LAB_WORKFLOW_SECTIONS,
  type QuantLabSection,
} from "@/lib/quantLabNavigation";
import { useTranslation } from "@/lib/i18n";
import clsx from "clsx";
import { useEffect, useRef, useState } from "react";

interface QuantLabSectionNavProps {
  section: QuantLabSection;
  onSectionChange: (section: QuantLabSection) => void;
}

export function QuantLabSectionNav({ section, onSectionChange }: QuantLabSectionNavProps) {
  const { t } = useTranslation();
  const [moreOpen, setMoreOpen] = useState(false);
  const moreRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!moreOpen) return;
    const onDoc = (e: MouseEvent) => {
      if (moreRef.current && !moreRef.current.contains(e.target as Node)) {
        setMoreOpen(false);
      }
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [moreOpen]);

  const sectionLabel: Record<QuantLabSection, string> = {
    overview: t.quantLab.navOverview,
    ideas: t.quantLab.navIdeas,
    experiments: t.quantLab.navExperiments,
    "factor-discovery": t.quantLab.navFactorDiscovery,
    results: t.quantLab.navResults,
    "model-monitor": t.quantLab.navModelMonitor,
    legacy: t.quantLab.navLegacy,
  };

  const overflowActive = (QUANT_LAB_OVERFLOW_SECTIONS as readonly string[]).includes(section);

  return (
    <div className="quant-lab-section-tabs quant-lab-nav">
      <AppTabBar aria-label={t.quantLab.navAria} className="quant-lab-nav__bar overflow-x-auto">
        <div className="quant-lab-nav__group" role="presentation">
          <span className="quant-lab-nav__group-label">{t.quantLab.navGroupWorkflow}</span>
          {QUANT_LAB_WORKFLOW_SECTIONS.map((key) => (
            <AppTabButton key={key} active={section === key} onClick={() => onSectionChange(key)}>
              {sectionLabel[key]}
            </AppTabButton>
          ))}
        </div>

        <AppTabButton
          active={section === "legacy"}
          onClick={() => onSectionChange("legacy")}
          className="quant-lab-section-tabs__legacy quant-lab-nav__legacy-inline"
        >
          {sectionLabel.legacy}
        </AppTabButton>

        <div className="quant-lab-nav__more" ref={moreRef}>
          <AppTabButton
            active={overflowActive}
            aria-expanded={moreOpen}
            aria-haspopup="menu"
            onClick={() => setMoreOpen((open) => !open)}
          >
            {t.quantLab.navMore}
          </AppTabButton>
          {moreOpen && (
            <div className="quant-lab-nav-more__menu" role="menu">
              {QUANT_LAB_OVERFLOW_SECTIONS.map((key) => (
                <button
                  key={key}
                  type="button"
                  role="menuitem"
                  className={clsx(
                    "quant-lab-nav-more__item",
                    section === key && "quant-lab-nav-more__item--active"
                  )}
                  onClick={() => {
                    onSectionChange(key);
                    setMoreOpen(false);
                  }}
                >
                  {sectionLabel[key]}
                </button>
              ))}
            </div>
          )}
        </div>
      </AppTabBar>
    </div>
  );
}
