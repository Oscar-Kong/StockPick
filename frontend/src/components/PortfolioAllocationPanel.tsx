"use client";

import { getAllocationRecommendation, exportToLean } from "@/lib/api";
import { ResearchWarning } from "@/components/ui/ResearchWarning";
import type { AllocationRecommendationResponse, Bucket, LeanExportResponse } from "@/lib/types";
import { fmt, useTranslation } from "@/lib/i18n";
import { useState } from "react";

interface PortfolioAllocationPanelProps {
  symbols: string[];
}

export function PortfolioAllocationPanel({ symbols }: PortfolioAllocationPanelProps) {
  const { t } = useTranslation();
  const [bucket, setBucket] = useState<Bucket>("medium");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AllocationRecommendationResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [exportLoading, setExportLoading] = useState(false);
  const [exportResult, setExportResult] = useState<LeanExportResponse | null>(null);

  const run = async () => {
    setLoading(true);
    setError(null);
    try {
      setResult(await getAllocationRecommendation(bucket, symbols.length ? symbols : undefined));
    } catch (e) {
      setError(e instanceof Error ? e.message : t.portfolio.allocationFailed);
    } finally {
      setLoading(false);
    }
  };

  const runExport = async () => {
    setExportLoading(true);
    try {
      setExportResult(
        await exportToLean({
          bucket,
          symbols: symbols.length ? symbols : undefined,
          include_latest_scan: true,
        })
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : t.portfolio.leanExportFailed);
    } finally {
      setExportLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      <ResearchWarning message={t.portfolio.allocationHeuristicWarning} />
      <div className="flex flex-wrap gap-2">
        <select
          value={bucket}
          onChange={(e) => setBucket(e.target.value as Bucket)}
          className="rounded border border-zinc-700 bg-zinc-950 px-2 py-1 text-sm"
        >
          <option value="penny">penny</option>
          <option value="medium">medium</option>
          <option value="compounder">compounder</option>
        </select>
        <button type="button" onClick={() => void run()} disabled={loading} className="btn-primary px-3 py-1.5 text-sm">
          {loading ? t.common.running : t.portfolio.runAllocation}
        </button>
        <button
          type="button"
          onClick={() => void runExport()}
          disabled={exportLoading}
          className="btn-ghost px-3 py-1.5 text-sm"
        >
          {exportLoading ? t.common.running : t.portfolio.exportLean}
        </button>
      </div>
      {error && <p className="text-sm text-red-400">{error}</p>}
      {result && (
        <div className="surface-card space-y-2 p-4">
          <p className="text-xs text-zinc-500">
            {result.model_name} · {result.source} · enabled={String(result.enabled)}
          </p>
          <ul className="text-sm">
            {result.target_weights.slice(0, 12).map((w) => (
              <li key={w.symbol} className="flex justify-between border-t border-zinc-900 py-1">
                <span>{w.symbol}</span>
                <span className="tabular-nums">{(w.target_weight * 100).toFixed(1)}%</span>
              </li>
            ))}
          </ul>
          {result.notes.map((n) => (
            <p key={n} className="text-xs text-zinc-500">
              {n}
            </p>
          ))}
        </div>
      )}
      {exportResult && (
        <p className="text-xs text-[#7dff8e]">
          {fmt(t.portfolio.leanExported, { id: exportResult.export_id })}
        </p>
      )}
    </div>
  );
}
