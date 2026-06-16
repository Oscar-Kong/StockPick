"use client";

import clsx from "clsx";

export type AppCardVariant = "default" | "elevated" | "muted" | "ghost";

const VARIANT: Record<AppCardVariant, string> = {
  default: "app-card",
  elevated: "app-card app-card--elevated",
  muted: "app-card app-card--muted",
  ghost: "app-card app-card--ghost",
};

interface AppCardProps {
  children: React.ReactNode;
  className?: string;
  variant?: AppCardVariant;
  as?: "div" | "section" | "article";
}

export function AppCard({ children, className, variant = "default", as: Tag = "div" }: AppCardProps) {
  return <Tag className={clsx(VARIANT[variant], className)}>{children}</Tag>;
}

interface SectionCardProps {
  title: string;
  subtitle?: string;
  action?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  variant?: AppCardVariant;
}

export function SectionCard({ title, subtitle, action, children, className, variant = "default" }: SectionCardProps) {
  return (
    <AppCard variant={variant} className={clsx("data-panel data-panel--padded", className)} as="section">
      <div className="data-panel-header">
        <div className="min-w-0">
          <h2 className="data-panel-title">{title}</h2>
          {subtitle && <p className="data-panel-subtitle">{subtitle}</p>}
        </div>
        {action}
      </div>
      {children}
    </AppCard>
  );
}
