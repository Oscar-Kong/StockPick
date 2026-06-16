"use client";

import clsx from "clsx";

interface PageContainerProps {
  children: React.ReactNode;
  className?: string;
  /** Standard data-heavy max width (~1520px). Default true. */
  constrained?: boolean;
  /** Full bleed — no max-width cap (e.g. workspace). */
  full?: boolean;
  as?: "div" | "section" | "main";
}

export function PageContainer({
  children,
  className,
  constrained = true,
  full = false,
  as: Tag = "div",
}: PageContainerProps) {
  return (
    <Tag
      className={clsx(
        "page-container",
        full && "page-container--full",
        !full && constrained && "page-container--constrained",
        className
      )}
    >
      {children}
    </Tag>
  );
}
