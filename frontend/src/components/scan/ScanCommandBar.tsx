"use client";

import { useTranslation } from "@/lib/i18n";
import type { ScanOptions } from "@/lib/types";
import clsx from "clsx";
import { useEffect, useRef, useState } from "react";

interface ScanCommandBarProps {
  options: ScanOptions;
  onChange: (options: ScanOptions) => void;
  onScan: () => void;
  onReset: () => void;
  scanning: boolean;
  advancedFilterCount: number;
  savedScansSlot?: React.ReactNode;
  saveSlot?: React.ReactNode;
  overflowSlot?: React.ReactNode;
}

const INPUT_COMPACT =
  "h-9 w-16 rounded-md border border-zinc-700 bg-zinc-950/80 px-2 text-sm tabular-nums text-zinc-100 outline-none focus:border-primary";

export function ScanCommandBar({
  options,
  onChange,
  onScan,
  onReset,
  scanning,
  advancedFilterCount,
  savedScansSlot,
  saveSlot,
  overflowSlot,
}: ScanCommandBarProps) {
  const { t } = useTranslation();
  const [filtersOpen, setFiltersOpen] = useState(false);
  const trayRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!filtersOpen) return;
    const onDoc = (e: MouseEvent) => {
      if (trayRef.current && !trayRef.current.contains(e.target as Node)) {
        setFiltersOpen(false);
      }
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [filtersOpen]);

  const advancedFields = [
    {
      key: "min_price",
      label: t.scan.minPrice,
      type: "number",
      step: "0.01",
      value: options.min_price ?? "",
      onChange: (v: string) => onChange({ ...options, min_price: v ? Number(v) : undefined }),
    },
    {
      key: "max_price",
      label: t.scan.maxPrice,
      type: "number",
      step: "0.01",
      value: options.max_price ?? "",
      onChange: (v: string) => onChange({ ...options, max_price: v ? Number(v) : undefined }),
    },
    {
      key: "min_volume",
      label: t.scan.minVolume,
      type: "number",
      value: options.min_volume ?? "",
      onChange: (v: string) => onChange({ ...options, min_volume: v ? Number(v) : undefined }),
    },
  ] as const;

  return (
    <div className="scan-command-bar">
      <div className="scan-command-bar__row">
        <label className="scan-command-bar__field">
          <span className="sr-only">{t.scan.maxResults}</span>
          <span className="scan-command-bar__label" aria-hidden>
            {t.scan.maxResultsShort}
          </span>
          <input
            type="number"
            min={5}
            max={50}
            value={options.max_results ?? 50}
            onChange={(e) => onChange({ ...options, max_results: Number(e.target.value) })}
            className={INPUT_COMPACT}
            title={t.scan.maxResultsHint}
          />
        </label>

        <div className="relative" ref={trayRef}>
          <button
            type="button"
            onClick={() => setFiltersOpen((o) => !o)}
            className={clsx("scan-command-bar__btn", filtersOpen && "scan-command-bar__btn--active")}
            aria-expanded={filtersOpen}
            aria-haspopup="dialog"
            title={t.scan.advancedFiltersHint}
          >
            {t.scan.advancedFilters}
            {advancedFilterCount > 0 && (
              <span className="scan-command-bar__badge">{advancedFilterCount}</span>
            )}
          </button>
          {filtersOpen && (
            <div className="scan-filter-tray" role="dialog" aria-label={t.scan.advancedFilters}>
              <div className="scan-filter-tray__grid">
                {advancedFields.map((field) => (
                  <label key={field.key} className="block">
                    <span className="scan-command-bar__label">{field.label}</span>
                    <input
                      type={field.type}
                      step={"step" in field ? field.step : undefined}
                      value={field.value}
                      onChange={(e) => field.onChange(e.target.value)}
                      className="input-field mt-1 h-9 text-sm"
                    />
                  </label>
                ))}
              </div>
            </div>
          )}
        </div>

        <button type="button" onClick={onReset} disabled={scanning} className="scan-command-bar__btn">
          {t.scan.resetFilters}
        </button>

        <button type="button" onClick={onScan} disabled={scanning} className="btn-primary scan-command-bar__run">
          {scanning ? t.common.scanning : t.scan.runScan}
        </button>

        <div className="scan-command-bar__spacer" />

        {savedScansSlot}
        {saveSlot}
        {overflowSlot}
      </div>
    </div>
  );
}

export function countAdvancedFilters(options: ScanOptions): number {
  let n = 0;
  if (options.min_price != null) n += 1;
  if (options.max_price != null) n += 1;
  if (options.min_volume != null) n += 1;
  return n;
}
