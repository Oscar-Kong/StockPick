"use client";

import clsx from "clsx";
import type { ButtonHTMLAttributes, ReactNode } from "react";

/** Filter / toggle control — uses aria-pressed, not tab semantics. */
export function FilterToggle({
  pressed,
  className,
  children,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { pressed?: boolean }) {
  return (
    <button
      type="button"
      className={clsx("filter-toggle", pressed && "filter-toggle--active", className)}
      aria-pressed={pressed ?? false}
      {...props}
    >
      {children}
    </button>
  );
}

/** Segmented single-choice control for non-route options. */
export function SegmentedControl({
  children,
  className,
  "aria-label": ariaLabel,
}: {
  children: ReactNode;
  className?: string;
  "aria-label"?: string;
}) {
  return (
    <div className={clsx("segmented-control", className)} role="group" aria-label={ariaLabel}>
      {children}
    </div>
  );
}

/** True content tabs — role=tablist for in-page view switching only. */
export function ContentTabList({
  children,
  className,
  "aria-label": ariaLabel,
}: {
  children: ReactNode;
  className?: string;
  "aria-label"?: string;
}) {
  return (
    <div className={clsx("content-tab-list", className)} role="tablist" aria-label={ariaLabel}>
      {children}
    </div>
  );
}

export function ContentTab({
  selected,
  className,
  children,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { selected?: boolean }) {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={selected ?? false}
      className={clsx("content-tab", selected && "content-tab--selected", className)}
      {...props}
    >
      {children}
    </button>
  );
}
