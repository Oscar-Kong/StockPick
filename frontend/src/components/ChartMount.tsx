// Defer Recharts until the container has measurable width and height.
"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";

function hasChartDimensions(el: HTMLElement): boolean {
  const { width, height } = el.getBoundingClientRect();
  // Require >1px — Recharts logs when ResponsiveContainer measures width/height as -1/0.
  return width > 1 && height > 1;
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
      if (!cancelled && hasChartDimensions(el)) setReady(true);
    };

    // Always observe — parent layout can settle after first paint (flex/grid).
    const ro = new ResizeObserver(() => {
      markReady();
      if (hasChartDimensions(el)) ro.disconnect();
    });
    ro.observe(el);
    markReady();

    rafId = requestAnimationFrame(() => {
      rafId = requestAnimationFrame(markReady);
    });

    return () => {
      cancelled = true;
      ro.disconnect();
      cancelAnimationFrame(rafId);
    };
  }, []);

  return (
    <div ref={ref} className={className} style={{ minWidth: 0 }}>
      {ready ? children : null}
    </div>
  );
}
