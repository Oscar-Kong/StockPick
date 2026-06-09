"use client";

import { ResearchWarning } from "@/components/ui/ResearchWarning";
import { ResearchOnlyBadge } from "@/components/ui/ResearchOnlyBadge";
import { TooltipLabel } from "@/components/ui/TooltipLabel";
import { runPairsResearch } from "@/lib/api";
import { parseApiError } from "@/lib/apiError";
import { PAIRS_MAX_SYMBOLS, parseSymbolList } from "@/lib/quantLabFormatters";
import { useTranslation } from "@/lib/i18n";
import { useState } from "react";
import { QuantLabEmptyState, QuantLabTabLayout } from "./QuantLabTabShell";

export function PairsTab() {
  const { t } = useTranslation();
  const [symbols, setSymbols] = useState("AAPL, MSFT, GOOGL");
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<Awaited<ReturnType<typeof runPairsResearch>> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);

  const run = async () => {
    setValidationError(null);
    setError(null);
    const list = parseSymbolList(symbols);
    if (list.length < 2) {
      setValidationError(t.quantLab.pairsMinSymbols);
      return;
    }
    if (list.length > PAIRS_MAX_SYMBOLS) {
      setValidationError(t.quantLab.pairsMaxSymbols.replace("{max}", String(PAIRS_MAX_SYMBOLS)));
      return;
    }

    setRunning(true);
    try {
      setResult(await runPairsResearch({ symbols: list, lookback_period: "1y" }));
    } catch (e) {
      setResult(null);
      setError(parseApiError(e, t.quantLab.runFailed));
    } finally {
      setRunning(false);
    }
  };

  const pairs = result?.pairs ?? [];
  const notes = result?.notes ?? [];

  return (
    <QuantLabTabLayout
      title={t.quantLab.tabPairs}
      statusBadge={<ResearchOnlyBadge tooltip={t.product.researchOnlyTooltip} />}
      description={
        <TooltipLabel label={t.quantLab.hintPairs} tooltip={t.quantLab.cointegrationTooltip} />
      }
      controls={
        <div className="space-y-3">
          <ResearchWarning message={t.quantLab.researchOnlyExtended} />
          <textarea
            value={symbols}
            onChange={(e) => setSymbols(e.target.value)}
            rows={2}
            className="w-full rounded-lg border border-zinc-700 bg-zinc-950 p-2 text-sm"
          />
          <p className="text-xs text-zinc-600">
            {t.quantLab.pairsSymbolHint.replace("{max}", String(PAIRS_MAX_SYMBOLS))}
          </p>
          <button
            type="button"
            onClick={() => void run()}
            disabled={running}
            className="btn-primary px-3 py-1.5 text-sm"
          >
            {running ? t.common.running : t.quantLab.runPairs}
          </button>
          {validationError && <p className="text-xs text-amber-300">{validationError}</p>}
        </div>
      }
      loading={running}
      error={error}
      onRetry={() => void run()}
    >
      {result && (
        <div className="space-y-3">
          <p className="text-xs text-zinc-500">
            {t.quantLab.pairsSummary}: {result.pairs_returned}/{result.pairs_evaluated} ·{" "}
            {t.quantLab.cointegrated}: {result.cointegrated_count}
            {!result.statsmodels_available && ` · ${t.quantLab.statsmodelsMissing}`}
          </p>
          {result.cointegrated_count === 0 && pairs.length > 0 && (
            <p className="text-xs text-amber-300/90">{t.quantLab.noCointegratedPairs}</p>
          )}
          {notes.length > 0 && (
            <ul className="list-inside list-disc text-xs text-zinc-500">
              {notes.map((note, i) => (
                <li key={i}>{note}</li>
              ))}
            </ul>
          )}
          {pairs.length === 0 ? (
            <QuantLabEmptyState message={t.quantLab.noPairs} />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[480px] text-xs">
                <thead>
                  <tr className="text-left text-zinc-500">
                    <th className="py-1 pr-2">{t.quantLab.pair}</th>
                    <th className="py-1 pr-2">p</th>
                    <th className="py-1 pr-2">z</th>
                    <th className="py-1">{t.quantLab.pairStatus}</th>
                  </tr>
                </thead>
                <tbody>
                  {pairs.slice(0, 15).map((p, index) => (
                    <tr
                      key={`${p.symbol_x}-${p.symbol_y}-${index}`}
                      className="border-t border-zinc-900"
                    >
                      <td className="py-2 pr-2">
                        {p.symbol_x || "?"}/{p.symbol_y || "?"}
                      </td>
                      <td className="py-2 pr-2 tabular-nums">
                        {p.p_value != null && Number.isFinite(p.p_value) ? p.p_value.toFixed(4) : "—"}
                      </td>
                      <td className="py-2 pr-2 tabular-nums">
                        {p.latest_z_score != null && Number.isFinite(p.latest_z_score)
                          ? p.latest_z_score.toFixed(2)
                          : "—"}
                      </td>
                      <td className="py-2 text-zinc-400">
                        {p.sufficient === false
                          ? p.warning ?? t.quantLab.insufficientData
                          : p.cointegrated_5pct
                            ? t.quantLab.cointegrated
                            : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
      {!result && !running && !error && (
        <QuantLabEmptyState message={t.quantLab.pairsNoRunYet} />
      )}
    </QuantLabTabLayout>
  );
}
