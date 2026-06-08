// Scan filter form and run button for bucket screening jobs.
"use client";

import { fmt, useTranslation } from "@/lib/i18n";
import type { ScanOptions } from "@/lib/types";

interface ScanControlsProps {
  bucketLabel: string;
  options: ScanOptions;
  onChange: (options: ScanOptions) => void;
  onScan: () => void;
  onReset: () => void;
  scanning: boolean;
}

export function ScanControls({
  bucketLabel,
  options,
  onChange,
  onScan,
  onReset,
  scanning,
}: ScanControlsProps) {
  const { t } = useTranslation();

  return (
    <div className="surface-card p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold text-zinc-100">
            {fmt(t.scan.filtersTitle, { label: bucketLabel })}
          </h2>
          <p className="mt-0.5 text-xs text-zinc-500">{t.scan.filtersStep}</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onReset}
            disabled={scanning}
            className="btn-ghost px-3 py-2 text-xs hover:bg-zinc-900 disabled:opacity-50"
          >
            {t.scan.resetFilters}
          </button>
          <button
            type="button"
            onClick={onScan}
            disabled={scanning}
            className="btn-primary px-4 py-2 text-sm disabled:opacity-50"
          >
            {scanning ? t.common.scanning : t.scan.runScan}
          </button>
        </div>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <label className="text-xs text-zinc-500">
          {t.scan.maxResults}
          <input
            type="number"
            min={5}
            max={50}
            value={options.max_results ?? 25}
            onChange={(e) =>
              onChange({ ...options, max_results: Number(e.target.value) })
            }
            className="mt-1 w-full rounded-lg border border-zinc-700 bg-zinc-950/80 px-3 py-2 text-sm text-zinc-100 outline-none focus:border-[#00c805]"
          />
        </label>
        <label className="text-xs text-zinc-500">
          {t.scan.minPrice}
          <input
            type="number"
            step="0.01"
            value={options.min_price ?? ""}
            onChange={(e) =>
              onChange({
                ...options,
                min_price: e.target.value ? Number(e.target.value) : undefined,
              })
            }
            className="mt-1 w-full rounded-lg border border-zinc-700 bg-zinc-950/80 px-3 py-2 text-sm text-zinc-100 outline-none focus:border-[#00c805]"
          />
        </label>
        <label className="text-xs text-zinc-500">
          {t.scan.maxPrice}
          <input
            type="number"
            step="0.01"
            value={options.max_price ?? ""}
            onChange={(e) =>
              onChange({
                ...options,
                max_price: e.target.value ? Number(e.target.value) : undefined,
              })
            }
            className="mt-1 w-full rounded-lg border border-zinc-700 bg-zinc-950/80 px-3 py-2 text-sm text-zinc-100 outline-none focus:border-[#00c805]"
          />
        </label>
        <label className="text-xs text-zinc-500">
          {t.scan.minVolume}
          <input
            type="number"
            value={options.min_volume ?? ""}
            onChange={(e) =>
              onChange({
                ...options,
                min_volume: e.target.value ? Number(e.target.value) : undefined,
              })
            }
            className="mt-1 w-full rounded-lg border border-zinc-700 bg-zinc-950/80 px-3 py-2 text-sm text-zinc-100 outline-none focus:border-[#00c805]"
          />
        </label>
      </div>
    </div>
  );
}
