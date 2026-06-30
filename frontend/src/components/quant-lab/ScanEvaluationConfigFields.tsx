"use client";

import { SCAN_EVAL_ALGORITHM_VERSIONS } from "@/lib/scanEvaluationDisplay";
import type { ExperimentPresetId } from "@/lib/experimentStudio";
import { useTranslation } from "@/lib/i18n";

interface ScanEvaluationConfigFieldsProps {
  params: Record<string, unknown>;
  preset: ExperimentPresetId;
  onChange: (next: Record<string, unknown>) => void;
}

export function ScanEvaluationConfigFields({ params, preset, onChange }: ScanEvaluationConfigFieldsProps) {
  const { t } = useTranslation();
  const versions = (params.algorithm_versions as string[]) ?? ["alphabetical_baseline", "stage_a_v2"];
  const horizons = (params.forward_horizons as number[]) ?? [5, 20];

  const toggleVersion = (ver: string) => {
    const next = versions.includes(ver) ? versions.filter((v) => v !== ver) : [...versions, ver];
    onChange({ ...params, algorithm_versions: next.length ? next : [ver] });
  };

  return (
    <div className="space-y-3 border-t border-zinc-800 pt-3">
      <p className="text-xs text-amber-200/90">{t.quantLab.scanEvalProductionNotice}</p>
      {preset === "scan_eval_smoke" && (
        <p className="text-xs text-zinc-500">{t.quantLab.scanEvalSmokePresetHint}</p>
      )}
      <div className="flex flex-wrap gap-3">
        <label className="text-xs text-zinc-500">
          {t.quantLab.startDate}
          <input
            type="date"
            value={String(params.start_date ?? "")}
            onChange={(e) => onChange({ ...params, start_date: e.target.value })}
            className="ml-2 rounded border border-zinc-700 bg-zinc-950 px-2 py-1"
          />
        </label>
        <label className="text-xs text-zinc-500">
          {t.quantLab.endDate}
          <input
            type="date"
            value={String(params.end_date ?? "")}
            onChange={(e) => onChange({ ...params, end_date: e.target.value })}
            className="ml-2 rounded border border-zinc-700 bg-zinc-950 px-2 py-1"
          />
        </label>
        <label className="text-xs text-zinc-500">
          {t.quantLab.scanEvalRebalance}
          <select
            value={String(params.rebalance_frequency ?? "monthly")}
            onChange={(e) => onChange({ ...params, rebalance_frequency: e.target.value })}
            className="ml-2 rounded border border-zinc-700 bg-zinc-950 px-2 py-1"
          >
            <option value="monthly">monthly</option>
            <option value="weekly">weekly</option>
          </select>
        </label>
      </div>
      <fieldset className="text-xs text-zinc-500">
        <legend className="mb-1 text-zinc-400">{t.quantLab.scanEvalAlgorithms}</legend>
        <div className="flex flex-wrap gap-2">
          {SCAN_EVAL_ALGORITHM_VERSIONS.map((ver) => (
            <label key={ver} className="flex items-center gap-1 rounded border border-zinc-800 px-2 py-1">
              <input type="checkbox" checked={versions.includes(ver)} onChange={() => toggleVersion(ver)} />
              {ver}
            </label>
          ))}
        </div>
      </fieldset>
      <div className="flex flex-wrap gap-3">
        <label className="text-xs text-zinc-500">
          {t.quantLab.scanEvalStageBCap}
          <input
            type="number"
            min={1}
            value={Number(params.stage_b_cap ?? 20)}
            onChange={(e) => onChange({ ...params, stage_b_cap: Number(e.target.value) })}
            className="ml-2 w-16 rounded border border-zinc-700 bg-zinc-950 px-2 py-1 tabular-nums"
          />
        </label>
        <label className="text-xs text-zinc-500">
          {t.quantLab.scanEvalMaxUniverse}
          <input
            type="number"
            min={1}
            value={Number(params.max_universe ?? 25)}
            onChange={(e) => onChange({ ...params, max_universe: Number(e.target.value) })}
            className="ml-2 w-16 rounded border border-zinc-700 bg-zinc-950 px-2 py-1 tabular-nums"
          />
        </label>
        <label className="text-xs text-zinc-500">
          {t.quantLab.forwardHorizons}
          <input
            value={horizons.join(", ")}
            onChange={(e) =>
              onChange({
                ...params,
                forward_horizons: e.target.value
                  .split(/[,\s]+/)
                  .filter(Boolean)
                  .map((x) => Number(x)),
              })
            }
            className="ml-2 w-24 rounded border border-zinc-700 bg-zinc-950 px-2 py-1 tabular-nums"
          />
        </label>
      </div>
      <div className="flex flex-wrap gap-3">
        <label className="text-xs text-zinc-500">
          {t.quantLab.scanEvalSpreadBps}
          <input
            type="number"
            value={Number(params.spread_bps ?? 50)}
            onChange={(e) => onChange({ ...params, spread_bps: Number(e.target.value) })}
            className="ml-2 w-16 rounded border border-zinc-700 bg-zinc-950 px-2 py-1 tabular-nums"
          />
        </label>
        <label className="text-xs text-zinc-500">
          {t.quantLab.scanEvalSlippageBps}
          <input
            type="number"
            value={Number(params.slippage_bps ?? 25)}
            onChange={(e) => onChange({ ...params, slippage_bps: Number(e.target.value) })}
            className="ml-2 w-16 rounded border border-zinc-700 bg-zinc-950 px-2 py-1 tabular-nums"
          />
        </label>
        <label className="flex items-center gap-2 text-xs text-zinc-500">
          <input
            type="checkbox"
            checked={Boolean(params.apply_penny_friction ?? true)}
            onChange={(e) => onChange({ ...params, apply_penny_friction: e.target.checked })}
          />
          {t.quantLab.scanEvalPennyFriction}
        </label>
      </div>
    </div>
  );
}
