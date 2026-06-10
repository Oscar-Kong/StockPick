"use client";

import { runPortfolioDailyDecision } from "@/lib/api";
import type { Bucket, PortfolioDecisionItem, PortfolioDecisionResponse, PortfolioHolding } from "@/lib/types";
import { fmt, useTranslation, useTRef } from "@/lib/i18n";
import { Fragment, useCallback, useState } from "react";

type HoldingRow = PortfolioHolding & { id: string };

function newRow(): HoldingRow {
  return {
    id: crypto.randomUUID(),
    symbol: "",
    shares: 100,
    avg_cost: 1,
    bucket: "penny",
  };
}

function DecisionBadge({ decision }: { decision: string }) {
  const colors: Record<string, string> = {
    buy: "text-[#7dff8e] border-[#7dff8e]/40 bg-[#7dff8e]/10",
    keep: "text-zinc-200 border-zinc-600 bg-zinc-800/60",
    sell: "text-red-300 border-red-500/40 bg-red-500/10",
    review: "text-amber-300 border-amber-500/40 bg-amber-500/10",
    watch: "text-sky-300 border-sky-500/40 bg-sky-500/10",
  };
  return (
    <span
      className={`inline-block rounded border px-1.5 py-0.5 text-[10px] font-medium uppercase ${colors[decision] ?? colors.keep}`}
    >
      {decision}
    </span>
  );
}

function ItemDetails({ item }: { item: PortfolioDecisionItem }) {
  const { t } = useTranslation();
  return (
    <div className="mt-2 space-y-1 rounded border border-zinc-800 bg-zinc-950/60 p-2 text-xs text-zinc-400">
      <p>
        {t.portfolio.dailyScore}: {item.score} · {t.portfolio.dailyRisk}: {item.risk_index}
      </p>
      {item.reasons.length > 0 && (
        <ul className="list-inside list-disc">
          {item.reasons.map((r) => (
            <li key={r}>{r}</li>
          ))}
        </ul>
      )}
      {item.risk_flags.length > 0 && (
        <p className="text-amber-400/90">
          {t.portfolio.dailyRiskFlags}: {item.risk_flags.join("; ")}
        </p>
      )}
    </div>
  );
}

export function PortfolioDailyDecisionsPanel() {
  const { t } = useTranslation();
  const tRef = useTRef();
  const [cash, setCash] = useState("5000");
  const [rows, setRows] = useState<HoldingRow[]>([newRow()]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<PortfolioDecisionResponse | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);

  const updateRow = (id: string, patch: Partial<HoldingRow>) => {
    setRows((prev) => prev.map((r) => (r.id === id ? { ...r, ...patch } : r)));
  };

  const run = useCallback(async () => {
    const holdings = rows
      .map(({ symbol, shares, avg_cost, bucket }) => ({
        symbol: symbol.trim().toUpperCase(),
        shares: Number(shares),
        avg_cost: Number(avg_cost),
        bucket,
      }))
      .filter((h) => h.symbol && h.shares > 0 && h.avg_cost > 0);

    if (!holdings.length) {
      setError(tRef.current.portfolio.dailyNeedHolding);
      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await runPortfolioDailyDecision({
        cash: Number(cash) || 0,
        holdings,
      });
      setResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : tRef.current.portfolio.dailyFailed);
    } finally {
      setLoading(false);
    }
  }, [cash, rows, tRef]);

  return (
    <div className="space-y-4">
      <p className="text-xs text-zinc-500">{t.portfolio.dailyDisclaimer}</p>

      <div className="grid gap-3 sm:grid-cols-2">
        <label className="block text-xs text-zinc-500">
          {t.portfolio.dailyCash}
          <input
            type="number"
            min={0}
            step={100}
            value={cash}
            onChange={(e) => setCash(e.target.value)}
            className="mt-1 w-full rounded border border-zinc-700 bg-zinc-950 px-2 py-1.5 text-sm"
          />
        </label>
      </div>

      <div className="space-y-2">
        <p className="label-caps">{t.portfolio.dailyHoldings}</p>
        {rows.map((row) => (
          <div
            key={row.id}
            className="grid gap-2 rounded-lg border border-zinc-800 bg-zinc-950/40 p-2 sm:grid-cols-5"
          >
            <input
              placeholder="SYM"
              value={row.symbol}
              onChange={(e) => updateRow(row.id, { symbol: e.target.value.toUpperCase() })}
              className="rounded border border-zinc-700 bg-zinc-950 px-2 py-1 text-sm uppercase"
            />
            <input
              type="number"
              min={0}
              step={1}
              value={row.shares}
              onChange={(e) => updateRow(row.id, { shares: Number(e.target.value) })}
              className="rounded border border-zinc-700 bg-zinc-950 px-2 py-1 text-sm"
              aria-label={t.portfolio.dailyShares}
            />
            <input
              type="number"
              min={0}
              step={0.01}
              value={row.avg_cost}
              onChange={(e) => updateRow(row.id, { avg_cost: Number(e.target.value) })}
              className="rounded border border-zinc-700 bg-zinc-950 px-2 py-1 text-sm"
              aria-label={t.portfolio.dailyAvgCost}
            />
            <select
              value={row.bucket}
              onChange={(e) => updateRow(row.id, { bucket: e.target.value as Bucket })}
              className="rounded border border-zinc-700 bg-zinc-950 px-2 py-1 text-sm"
            >
              <option value="penny">{t.buckets.penny.label}</option>
              <option value="compounder">{t.buckets.compounder.label}</option>
            </select>
            <button
              type="button"
              onClick={() => setRows((p) => p.filter((r) => r.id !== row.id))}
              className="text-xs text-zinc-500 hover:text-red-400"
              disabled={rows.length <= 1}
            >
              {t.portfolio.dailyRemove}
            </button>
          </div>
        ))}
        <button
          type="button"
          onClick={() => setRows((p) => [...p, newRow()])}
          className="text-xs text-[#7dff8e] hover:underline"
        >
          {t.portfolio.dailyAddRow}
        </button>
      </div>

      <button
        type="button"
        onClick={() => void run()}
        disabled={loading}
        className="rounded-lg bg-[#00c805] px-4 py-2 text-sm font-medium text-black disabled:opacity-50"
      >
        {loading ? t.portfolio.dailyRunning : t.portfolio.dailyRunBtn}
      </button>

      {error && <p className="text-xs text-red-400">{error}</p>}

      {result && (
        <div className="space-y-2">
          <p className="text-xs text-zinc-500">
            {fmt(t.portfolio.dailyTotal, {
              value: result.total_value.toLocaleString(undefined, { maximumFractionDigits: 0 }),
              cash: result.cash.toLocaleString(undefined, { maximumFractionDigits: 0 }),
            })}
          </p>
          <div className="overflow-x-auto rounded-lg border border-zinc-800">
            <table className="w-full min-w-[900px] text-left text-xs">
              <thead className="border-b border-zinc-800 text-zinc-500">
                <tr>
                  <th className="p-2">{t.portfolio.dailyColSymbol}</th>
                  <th className="p-2">{t.portfolio.dailyColBucket}</th>
                  <th className="p-2">{t.portfolio.dailyColMktVal}</th>
                  <th className="p-2">{t.portfolio.dailyColCurWt}</th>
                  <th className="p-2">{t.portfolio.dailyColTgtWt}</th>
                  <th className="p-2">{t.portfolio.dailyColBuy}</th>
                  <th className="p-2">{t.portfolio.dailyColKeep}</th>
                  <th className="p-2">{t.portfolio.dailyColSell}</th>
                  <th className="p-2">{t.portfolio.dailyColDecision}</th>
                  <th className="p-2">{t.portfolio.dailyColAction}</th>
                  <th className="p-2">{t.portfolio.dailyColFlags}</th>
                </tr>
              </thead>
              <tbody>
                {result.items.map((item) => (
                  <Fragment key={item.symbol}>
                    <tr
                      className="border-b border-zinc-900 hover:bg-zinc-900/40 cursor-pointer"
                      onClick={() =>
                        setExpanded((e) => (e === item.symbol ? null : item.symbol))
                      }
                    >
                      <td className="p-2 font-medium text-zinc-100">{item.symbol}</td>
                      <td className="p-2 capitalize">{item.bucket}</td>
                      <td className="p-2 tabular-nums">${item.market_value.toLocaleString()}</td>
                      <td className="p-2 tabular-nums">{item.current_weight}%</td>
                      <td className="p-2 tabular-nums">{item.target_weight}%</td>
                      <td className="p-2 tabular-nums">{item.buy_pct}%</td>
                      <td className="p-2 tabular-nums">{item.keep_pct}%</td>
                      <td className="p-2 tabular-nums">{item.sell_pct}%</td>
                      <td className="p-2">
                        <DecisionBadge decision={item.decision} />
                      </td>
                      <td className="p-2 tabular-nums">
                        {item.suggested_dollar_action >= 0 ? "+" : ""}$
                        {item.suggested_dollar_action.toLocaleString()}
                      </td>
                      <td className="p-2 text-amber-400/80">{item.risk_flags.slice(0, 2).join(", ")}</td>
                    </tr>
                    {expanded === item.symbol && (
                      <tr>
                        <td colSpan={11} className="p-2">
                          <ItemDetails item={item} />
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>
          {result.notes.length > 0 && (
            <ul className="list-inside list-disc text-[10px] text-zinc-600">
              {result.notes.map((n) => (
                <li key={n}>{n}</li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
