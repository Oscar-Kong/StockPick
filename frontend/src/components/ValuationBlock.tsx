"use client";

import { useTranslation } from "@/lib/i18n";
import type { ValuationV2 } from "@/lib/types";
import clsx from "clsx";

const VERDICT_STYLE: Record<string, string> = {
  cheap: "text-emerald-300",
  fair: "text-zinc-200",
  expensive: "text-amber-300",
  extremely_expensive: "text-red-300",
};

export function ValuationBlock({ data }: { data: ValuationV2 }) {
  const { t } = useTranslation();
  const verdictKey = (data.verdict ?? "fair") as keyof typeof t.quant.verdicts;
  const verdict = t.quant.verdicts[verdictKey] ?? (data.verdict ?? "fair").replace(/_/g, " ");
  const grid = data.sensitivity_grid;
  const hasGrid =
    grid?.wacc?.length &&
    grid?.terminal_growth?.length &&
    grid?.values?.length;

  return (
    <div className="space-y-2 rounded-lg border border-zinc-800 bg-zinc-950/50 p-3 text-xs">
      <div className="flex items-center justify-between">
        <span className="font-medium text-zinc-300">{t.quant.valuation}</span>
        <span className={clsx("font-semibold capitalize", VERDICT_STYLE[data.verdict ?? "fair"])}>
          {verdict}
        </span>
      </div>
      <div className="grid grid-cols-2 gap-2 tabular-nums text-zinc-300">
        <div>
          {t.quant.dcfFair}{" "}
          {data.dcf_fair_value != null ? `$${data.dcf_fair_value.toFixed(0)}` : "—"}
        </div>
        <div>
          {t.quant.peerFair}{" "}
          {data.peer_fair_value != null ? `$${data.peer_fair_value.toFixed(0)}` : "—"}
        </div>
        <div>
          {t.quant.bullPrice}{" "}
          {data.dcf_bull != null ? `$${data.dcf_bull.toFixed(0)}` : "—"}
        </div>
        <div>
          {t.quant.bearPrice}{" "}
          {data.dcf_bear != null ? `$${data.dcf_bear.toFixed(0)}` : "—"}
        </div>
        <div>
          {t.quant.mos}{" "}
          {data.margin_of_safety_pct != null ? `${data.margin_of_safety_pct.toFixed(1)}%` : "—"}
        </div>
        <div>
          {t.quant.impliedGrowth}{" "}
          {data.reverse_dcf_implied_growth_pct != null
            ? `${data.reverse_dcf_implied_growth_pct.toFixed(1)}%`
            : "—"}
        </div>
      </div>
      {hasGrid && (
        <div className="overflow-x-auto pt-1">
          <p className="mb-1 text-xs uppercase tracking-wide text-zinc-500">
            {t.quant.dcfSensitivity}
          </p>
          <table className="w-full min-w-[240px] text-xs tabular-nums">
            <thead>
              <tr className="text-zinc-500">
                <th className="py-0.5 pr-1 text-left">{t.quant.waccG}</th>
                {grid!.terminal_growth!.map((g) => (
                  <th key={g} className="px-1 py-0.5 text-right">
                    {(g * 100).toFixed(1)}%
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {grid!.wacc!.map((w, ri) => (
                <tr key={w} className="border-t border-zinc-800/80">
                  <td className="py-0.5 pr-1 text-zinc-400">{(w * 100).toFixed(1)}%</td>
                  {grid!.values![ri]?.map((v, ci) => (
                    <td key={ci} className="px-1 py-0.5 text-right text-zinc-300">
                      {v != null ? `$${v.toFixed(0)}` : "—"}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
