"use client";

import clsx from "clsx";
import { AppCard, type AppCardVariant } from "./AppCard";

interface DataPanelProps {
  children: React.ReactNode;
  className?: string;
  variant?: AppCardVariant;
  /** Skip inner padding when children manage their own (e.g. tables). */
  flush?: boolean;
  as?: "div" | "section" | "article";
}

export function DataPanel({
  children,
  className,
  variant = "default",
  flush = false,
  as = "section",
}: DataPanelProps) {
  return (
    <AppCard variant={variant} as={as} className={clsx("data-panel", !flush && "data-panel--padded", className)}>
      {children}
    </AppCard>
  );
}

interface DataPanelHeaderProps {
  title: string;
  subtitle?: string;
  action?: React.ReactNode;
  className?: string;
}

export function DataPanelHeader({ title, subtitle, action, className }: DataPanelHeaderProps) {
  return (
    <div className={clsx("data-panel-header", className)}>
      <div className="min-w-0">
        <h2 className="data-panel-title">{title}</h2>
        {subtitle && <p className="data-panel-subtitle">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}
