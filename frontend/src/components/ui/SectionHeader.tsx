"use client";

import clsx from "clsx";

interface SectionHeaderProps {
  title: string;
  subtitle?: string;
  action?: React.ReactNode;
  className?: string;
}

export function SectionHeader({ title, subtitle, action, className }: SectionHeaderProps) {
  return (
    <div className={clsx("mb-3 flex flex-wrap items-start justify-between gap-2", className)}>
      <div className="min-w-0">
        <h2 className="section-title">{title}</h2>
        {subtitle && <p className="section-subtitle mt-0.5">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}
