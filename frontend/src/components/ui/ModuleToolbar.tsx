"use client";

import clsx from "clsx";

interface ModuleToolbarProps {
  children: React.ReactNode;
  className?: string;
  /** Primary row (title, actions). */
  leading?: React.ReactNode;
  /** Secondary row (filters, meta). */
  trailing?: React.ReactNode;
}

export function ModuleToolbar({ children, className, leading, trailing }: ModuleToolbarProps) {
  return (
    <div className={clsx("module-toolbar", className)}>
      {(leading || children) && (
        <div className="module-toolbar__row">
          {leading}
          {children}
        </div>
      )}
      {trailing && <div className="module-toolbar__row module-toolbar__row--secondary">{trailing}</div>}
    </div>
  );
}

export function ModuleToolbarMeta({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={clsx("module-toolbar__meta", className)}>{children}</div>;
}
