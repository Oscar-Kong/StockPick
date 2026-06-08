// Shared segmented tab bar (nav, workspace, scan, library, analysis).
"use client";

import clsx from "clsx";
import Link from "next/link";
import type { ButtonHTMLAttributes, ReactNode } from "react";

export function AppTabBar({
  children,
  className,
  "aria-label": ariaLabel,
}: {
  children: ReactNode;
  className?: string;
  "aria-label"?: string;
}) {
  return (
    <nav className={clsx("app-tab-bar", className)} aria-label={ariaLabel}>
      {children}
    </nav>
  );
}

export function AppTabButton({
  active,
  className,
  children,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { active?: boolean }) {
  return (
    <button
      type="button"
      className={clsx("app-tab", active && "app-tab--active", className)}
      {...props}
    >
      {children}
    </button>
  );
}

export function AppTabLink({
  active,
  href,
  className,
  children,
}: {
  active?: boolean;
  href: string;
  className?: string;
  children: ReactNode;
}) {
  return (
    <Link href={href} className={clsx("app-tab", active && "app-tab--active", className)}>
      {children}
    </Link>
  );
}
