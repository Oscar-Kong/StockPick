"use client";

import clsx from "clsx";
import { Surface, type SurfaceVariant } from "./Surface";

export type AppCardVariant = "default" | "elevated" | "muted" | "ghost";

const LEGACY_VARIANT: Record<AppCardVariant, SurfaceVariant> = {
  default: "default",
  elevated: "raised",
  muted: "inset",
  ghost: "default",
};

interface AppCardProps {
  children: React.ReactNode;
  className?: string;
  variant?: AppCardVariant;
  as?: "div" | "section" | "article";
}

/** Legacy card wrapper — prefer Surface for new code. */
export function AppCard({ children, className, variant = "default", as: Tag = "div" }: AppCardProps) {
  const surfaceVariant = LEGACY_VARIANT[variant];
  const ghostClass = variant === "ghost" ? "app-card app-card--ghost" : undefined;
  return (
    <Surface as={Tag} variant={surfaceVariant} className={clsx(ghostClass, className)}>
      {children}
    </Surface>
  );
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

export { Surface, SurfaceLink, InteractiveSurface } from "./Surface";
export type { SurfaceVariant } from "./Surface";
