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

const INPUT_CLASS =
  "mt-1.5 w-full rounded-lg border border-zinc-700 bg-zinc-950/80 px-3 py-2.5 text-sm text-zinc-100 outline-none focus:border-primary";

export function ScanControls({
  bucketLabel,
  options,
  onChange,
  onScan,
  onReset,
  scanning,
}: ScanControlsProps) {
  const { t } = useTranslation();

  const advancedFields = [
    {
      key: "min_price",
      label: t.scan.minPrice,
      hint: t.scan.minPriceHint,
      type: "number",
      step: "0.01",
      value: options.min_price ?? "",
      onChange: (v: string) =>
        onChange({ ...options, min_price: v ? Number(v) : undefined }),
    },
    {
      key: "max_price",
      label: t.scan.maxPrice,
      hint: t.scan.maxPriceHint,
      type: "number",
      step: "0.01",
      value: options.max_price ?? "",
      onChange: (v: string) =>
        onChange({ ...options, max_price: v ? Number(v) : undefined }),
    },
    {
      key: "min_volume",
      label: t.scan.minVolume,
      hint: t.scan.minVolumeHint,
      type: "number",
      value: options.min_volume ?? "",
      onChange: (v: string) =>
        onChange({ ...options, min_volume: v ? Number(v) : undefined }),
    },
  ] as const;

  return (
    <div className="surface-card p-4 sm:p-5">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div className="max-w-xl">
          <h2 className="text-sm font-semibold text-zinc-100">
            {fmt(t.scan.filtersTitle, { label: bucketLabel })}
          </h2>
          <p className="mt-1 text-xs leading-relaxed text-zinc-500">{t.scan.filtersSubtitleSimple}</p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
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
            className="btn-action px-4 py-2.5 text-sm disabled:opacity-50"
          >
            {scanning ? t.common.scanning : t.scan.runScan}
          </button>
        </div>
      </div>

      <div className="grid gap-4 sm:max-w-xs">
        <label className="block">
          <span className="text-xs font-medium text-zinc-300">{t.scan.maxResults}</span>
          <input
            type="number"
            min={5}
            max={50}
            value={options.max_results ?? 50}
            onChange={(e) => onChange({ ...options, max_results: Number(e.target.value) })}
            className={INPUT_CLASS}
          />
          <span className="mt-1.5 block text-sm leading-relaxed text-zinc-500">
            {t.scan.maxResultsHint}
          </span>
        </label>
      </div>

      <details className="mt-4 rounded-lg border border-zinc-800/80 bg-zinc-950/40 px-3 py-2">
        <summary className="cursor-pointer select-none text-xs font-medium text-zinc-400 hover:text-zinc-200">
          {t.scan.advancedFilters}
        </summary>
        <p className="mt-2 text-sm leading-relaxed text-zinc-500">{t.scan.advancedFiltersHint}</p>
        <div className="mt-3 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {advancedFields.map((field) => (
            <label key={field.key} className="block">
              <span className="text-xs font-medium text-zinc-300">{field.label}</span>
              <input
                type={field.type}
                step={"step" in field ? field.step : undefined}
                value={field.value}
                onChange={(e) => field.onChange(e.target.value)}
                className={INPUT_CLASS}
              />
              <span className="mt-1.5 block text-sm leading-relaxed text-zinc-500">{field.hint}</span>
            </label>
          ))}
        </div>
      </details>
    </div>
  );
}
