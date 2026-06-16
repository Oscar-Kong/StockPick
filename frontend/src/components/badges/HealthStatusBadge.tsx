"use client";

import clsx from "clsx";
import { useTranslation } from "@/lib/i18n";
import type { QuantHealthSeverity } from "@/lib/types";

interface HealthStatusBadgeProps {
  severity: QuantHealthSeverity;
  label?: string;
  className?: string;
}

const STYLE: Record<QuantHealthSeverity, string> = {
  ok: "border-emerald-500/30 bg-emerald-950/30 text-emerald-300",
  warning: "border-amber-500/30 bg-amber-950/30 text-amber-200",
  error: "border-red-500/40 bg-red-950/30 text-red-300",
};

export function HealthStatusBadge({ severity, label, className }: HealthStatusBadgeProps) {
  const { t } = useTranslation();
  const text =
    label ??
    (severity === "ok"
      ? t.quantHealth.statusOk
      : severity === "warning"
        ? t.quantHealth.statusWarning
        : t.quantHealth.statusError);

  return (
    <span className={clsx("chip px-2 py-0.5 text-xs font-medium uppercase", STYLE[severity], className)}>
      {text}
    </span>
  );
}
