"use client";

import clsx from "clsx";
import Link from "next/link";
import type { ComponentPropsWithoutRef, ElementType } from "react";

export type SurfaceVariant = "default" | "raised" | "interactive" | "data" | "inset" | "overlay";

const VARIANT_CLASS: Record<SurfaceVariant, string> = {
  default: "surface surface--default",
  raised: "surface surface--raised",
  interactive: "surface surface--interactive",
  data: "surface surface--data",
  inset: "surface surface--inset",
  overlay: "surface surface--overlay",
};

type SurfaceProps<T extends ElementType = "div"> = {
  as?: T;
  variant?: SurfaceVariant;
  className?: string;
  children: React.ReactNode;
} & Omit<ComponentPropsWithoutRef<T>, "as" | "className" | "children">;

/** Shared surface/card primitive with semantic variants. */
export function Surface<T extends ElementType = "div">({
  as,
  variant = "default",
  className,
  children,
  ...props
}: SurfaceProps<T>) {
  const Tag = as ?? "div";
  return (
    <Tag className={clsx(VARIANT_CLASS[variant], className)} {...props}>
      {children}
    </Tag>
  );
}

interface InteractiveSurfaceProps extends Omit<ComponentPropsWithoutRef<"button">, "className"> {
  className?: string;
  variant?: SurfaceVariant;
  children: React.ReactNode;
}

export function InteractiveSurface({
  className,
  variant = "interactive",
  children,
  type = "button",
  ...props
}: InteractiveSurfaceProps) {
  return (
    <button type={type} className={clsx(VARIANT_CLASS[variant], className)} {...props}>
      {children}
    </button>
  );
}

interface SurfaceLinkProps extends ComponentPropsWithoutRef<typeof Link> {
  variant?: SurfaceVariant;
}

export function SurfaceLink({ className, variant = "interactive", children, ...props }: SurfaceLinkProps) {
  return (
    <Link className={clsx(VARIANT_CLASS[variant], className)} {...props}>
      {children}
    </Link>
  );
}
