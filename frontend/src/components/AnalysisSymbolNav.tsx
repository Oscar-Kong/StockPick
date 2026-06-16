"use client";

import { fmt, useTranslation } from "@/lib/i18n";
import clsx from "clsx";
import { useEffect } from "react";

interface AnalysisSymbolNavProps {
  symbol: string;
  prevSymbol?: string | null;
  nextSymbol?: string | null;
  onNavigate?: (symbol: string) => void;
  className?: string;
}

export function AnalysisSymbolNav({
  symbol,
  prevSymbol,
  nextSymbol,
  onNavigate,
  className,
}: AnalysisSymbolNavProps) {
  const { t } = useTranslation();

  useEffect(() => {
    if (!onNavigate) return;
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      if (
        target &&
        (target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.tagName === "SELECT" ||
          target.isContentEditable)
      ) {
        return;
      }
      if (e.key === "[" && prevSymbol) {
        e.preventDefault();
        onNavigate(prevSymbol);
      }
      if (e.key === "]" && nextSymbol) {
        e.preventDefault();
        onNavigate(nextSymbol);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onNavigate, prevSymbol, nextSymbol]);

  if (!onNavigate || (!prevSymbol && !nextSymbol)) return null;

  return (
    <div className={clsx("analysis-symbol-nav", className)}>
      <button
        type="button"
        disabled={!prevSymbol}
        onClick={() => prevSymbol && onNavigate(prevSymbol)}
        className="analysis-symbol-nav-btn"
        aria-label={prevSymbol ? fmt(t.analysis.prevSymbol, { symbol: prevSymbol }) : t.analysis.noPrevSymbol}
        title={prevSymbol ? fmt(t.analysis.prevSymbol, { symbol: prevSymbol }) : undefined}
      >
        ←
      </button>
      <span className="analysis-symbol-nav-current">{symbol}</span>
      <button
        type="button"
        disabled={!nextSymbol}
        onClick={() => nextSymbol && onNavigate(nextSymbol)}
        className="analysis-symbol-nav-btn"
        aria-label={nextSymbol ? fmt(t.analysis.nextSymbol, { symbol: nextSymbol }) : t.analysis.noNextSymbol}
        title={nextSymbol ? fmt(t.analysis.nextSymbol, { symbol: nextSymbol }) : undefined}
      >
        →
      </button>
    </div>
  );
}
