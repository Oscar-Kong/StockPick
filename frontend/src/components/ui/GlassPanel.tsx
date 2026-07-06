"use client";

import clsx from "clsx";
import type { HTMLAttributes, ElementType } from "react";

export type GlassPanelVariant = "default" | "compact" | "hero";

export interface GlassPanelProps extends HTMLAttributes<HTMLElement> {
  variant?: GlassPanelVariant;
  as?: ElementType;
}

/**
 * Frosted glass surface with optional hero ambient glow — matches Analyze workspace panels.
 */
export function GlassPanel({
  variant = "default",
  as: Tag = "section",
  className,
  children,
  ...props
}: GlassPanelProps) {
  const isHero = variant === "hero";

  return (
    <Tag
      className={clsx(
        isHero ? "analysis-hero" : "analysis-glass-panel",
        !isHero && variant === "compact" && "analysis-glass-panel--compact",
        className,
      )}
      {...props}
    >
      {isHero && <div className="analysis-hero__ambient" aria-hidden />}
      {isHero ? <div className="pq-glass-panel__body">{children}</div> : children}
    </Tag>
  );
}
