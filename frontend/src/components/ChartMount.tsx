// Defer Recharts until the container has measurable width and height.
"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";

function hasChartDimensions(el: HTMLElement): boolean {
  const { width, height } = el.getBoundingClientRect();
  return width > 0 && height > 0;
}

export function ChartMount({
  className,
  children,
}: {
  className?: string;
  children: ReactNode;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    let cancelled = false;
    let rafId = 0;

    const markReady = () => {
      if (!cancelled) setReady(true);
    };

    if (hasChartDimensions(el)) {
      markReady();
      return;
    }

    const ro = new ResizeObserver(() => {
      if (hasChartDimensions(el)) {
        markReady();
        ro.disconnect();
      }
    });
    ro.observe(el);

    rafId = requestAnimationFrame(() => {
      rafId = requestAnimationFrame(() => {
        if (hasChartDimensions(el)) {
          markReady();
          ro.disconnect();
        }
      });
    });

    return () => {
      cancelled = true;
      ro.disconnect();
      cancelAnimationFrame(rafId);
    };
  }, []);

  return (
    <div ref={ref} className={className}>
      {ready ? children : null}
    </div>
  );
}
