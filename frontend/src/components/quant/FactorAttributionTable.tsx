"use client";

import { fmtNum } from "@/components/AsyncSection";
import type { FactorContributionV2 } from "@/lib/types";
import { useTranslation } from "@/lib/i18n";

interface FactorAttributionTableProps {
  factors: FactorContributionV2[];
  maxRows?: number;
}

export function FactorAttributionTable({ factors, maxRows }: FactorAttributionTableProps) {
  const { t } = useTranslation();
  const rows = maxRows ? factors.slice(0, maxRows) : factors;

  if (rows.length === 0) {
    return <p className="text-xs text-zinc-500">{t.quant.noFactorData}</p>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[420px] text-left text-xs">
        <thead>
          <tr className="border-b border-zinc-800 text-zinc-500">
            <th className="py-2 pr-3 font-medium">{t.common.field}</th>
            <th className="py-2 pr-3 font-medium">{t.common.score}</th>
            <th className="py-2 pr-3 font-medium">{t.common.weight}</th>
            <th className="py-2 font-medium">{t.quant.contribution}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((f) => (
            <tr key={f.factor_id} className="border-b border-zinc-900/80">
              <td className="py-2 pr-3 text-zinc-200">{f.display_name || f.factor_id}</td>
              <td className="py-2 pr-3 tabular-nums text-zinc-300">{fmtNum(f.norm_score, 1)}</td>
              <td className="py-2 pr-3 tabular-nums text-zinc-400">{fmtNum(f.weight, 2)}</td>
              <td
                className={`py-2 tabular-nums ${f.contribution >= 0 ? "text-emerald-300" : "text-red-300"}`}
              >
                {f.contribution >= 0 ? "+" : ""}
                {fmtNum(f.contribution, 2)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
