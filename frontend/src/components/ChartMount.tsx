// Defer Recharts until after layout so ResponsiveContainer gets real dimensions.
"use client";

import { useEffect, useState, type ReactNode } from "react";

export function ChartMount({
  className,
  children,
}: {
  className?: string;
  children: ReactNode;
}) {
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const id = requestAnimationFrame(() => setReady(true));
    return () => cancelAnimationFrame(id);
  }, []);

  return <div className={className}>{ready ? children : null}</div>;
}
