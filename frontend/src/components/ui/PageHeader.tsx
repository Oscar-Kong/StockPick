"use client";

import clsx from "clsx";
import type { ReactNode } from "react";
import { PageLead, PageTitle } from "./typography";

interface PageHeaderProps {
  title: string;
  subtitle?: ReactNode;
  actions?: ReactNode;
  className?: string;
}

export function PageHeader({ title, subtitle, actions, className }: PageHeaderProps) {
  return (
    <header className={clsx("page-header", className)}>
      <div className="min-w-0 flex-1">
        <PageTitle>{title}</PageTitle>
        {subtitle && <PageLead>{subtitle}</PageLead>}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
    </header>
  );
}
