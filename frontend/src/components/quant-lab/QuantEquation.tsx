"use client";

import katex from "katex";
import { useEffect, useRef } from "react";

interface QuantEquationProps {
  tex: string;
  display?: boolean;
  className?: string;
}

export function QuantEquation({ tex, display = true, className = "" }: QuantEquationProps) {
  const ref = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    if (!ref.current) return;
    try {
      katex.render(tex, ref.current, {
        displayMode: display,
        throwOnError: false,
        strict: "ignore",
      });
    } catch {
      ref.current.textContent = tex;
    }
  }, [tex, display]);

  return (
    <span
      ref={ref}
      className={`block overflow-x-auto py-1 text-zinc-100 ${display ? "text-center" : ""} ${className}`}
      aria-label={tex}
    />
  );
}
