"use client";

import clsx from "clsx";

type ButtonSize = "sm" | "md";

const SIZE: Record<ButtonSize, string> = {
  sm: "px-3.5 py-2 text-sm",
  md: "px-5 py-2.5 text-sm",
};

interface ButtonBaseProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  size?: ButtonSize;
  className?: string;
}

export function PrimaryButton({ size = "md", className, children, ...props }: ButtonBaseProps) {
  return (
    <button type="button" className={clsx("btn-primary font-medium", SIZE[size], className)} {...props}>
      {children}
    </button>
  );
}

export function SecondaryButton({ size = "md", className, children, ...props }: ButtonBaseProps) {
  return (
    <button type="button" className={clsx("btn-secondary font-medium", SIZE[size], className)} {...props}>
      {children}
    </button>
  );
}

export function GhostButton({ size = "md", className, children, ...props }: ButtonBaseProps) {
  return (
    <button type="button" className={clsx("btn-ghost font-medium", SIZE[size], className)} {...props}>
      {children}
    </button>
  );
}
