// Public-source trader strategy profiles and integration recipes.
"use client";

import { getTraderPreset, getTraderQuickCompare, listTraderIntelProfiles } from "@/lib/api";
import { formatDateTime } from "@/lib/datetime";
import { fmt, useTranslation } from "@/lib/i18n";
import type { Bucket, TraderProfileItem, TraderQuickCompareResponse } from "@/lib/types";
import Link from "next/link";
import { useEffect, useState } from "react";

function reliabilityTone(value: string): string {
  const v = value.toLowerCase();
  if (v.includes("high")) return "text-emerald-300 border-emerald-500/40 bg-emerald-500/10";
  if (v.includes("medium")) return "text-amber-300 border-amber-500/40 bg-amber-500/10";
  return "text-red-300 border-red-500/40 bg-red-500/10";
}

export default function TraderIntelPage() {
  const { t } = useTranslation();
  const [profiles, setProfiles] = useState<TraderProfileItem[]>([]);
  const [notes, setNotes] = useState<string[]>([]);
  const [collectedAt, setCollectedAt] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedBucketBySlug, setSelectedBucketBySlug] = useState<Record<string, Bucket>>({});
  const [compareBySlug, setCompareBySlug] = useState<Record<string, TraderQuickCompareResponse>>({});
  const [actionMsg, setActionMsg] = useState<string | null>(null);

  useEffect(() => {
    listTraderIntelProfiles()
      .then((res) => {
        setProfiles(res.profiles);
        setNotes(res.notes);
        setCollectedAt(res.collected_at_utc);
        const bucketMap: Record<string, Bucket> = {};
        res.profiles.forEach((p) => {
          const first = (p.integration_recipe.bucket_bias[0] as Bucket | undefined) ?? "medium";
          bucketMap[p.slug] = first;
        });
        setSelectedBucketBySlug(bucketMap);
      })
      .catch((err) => setError(err instanceof Error ? err.message : t.traderIntel.loadFailed))
      .finally(() => setLoading(false));
  }, [t.traderIntel.loadFailed]);

  return (
    <div className="space-y-6">
      <div className="surface-card p-5">
        <h1 className="text-2xl font-semibold tracking-tight text-zinc-100">{t.traderIntel.title}</h1>
        <p className="mt-1 text-sm text-zinc-500">{t.traderIntel.subtitle}</p>
        <p className="mt-2 text-xs text-zinc-500">
          {t.traderIntel.collected} {formatDateTime(collectedAt)}
        </p>
      </div>

      {notes.length > 0 && (
        <div className="surface-card p-4">
          <p className="text-xs font-medium text-zinc-300">{t.traderIntel.datasetNotes}</p>
          <ul className="mt-2 space-y-1 text-xs text-zinc-500">
            {notes.map((n) => (
              <li key={n}>• {n}</li>
            ))}
          </ul>
        </div>
      )}

      {loading && <p className="text-sm text-zinc-500">{t.traderIntel.loading}</p>}
      {error && <p className="text-sm text-red-400">{error}</p>}

      <div className="space-y-4">
        {profiles.map((p) => (
          <div key={p.slug} className="surface-card space-y-3 p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <h2 className="text-lg font-semibold text-zinc-100">{p.name}</h2>
                <p className="text-xs text-zinc-500">{p.profile_type}</p>
              </div>
              <span className={`rounded-full border px-2 py-0.5 text-xs ${reliabilityTone(p.data_reliability)}`}>
                {t.traderIntel.reliability} {p.data_reliability}
              </span>
            </div>
            <p className="text-sm text-zinc-400">{p.summary}</p>

            <div className="flex flex-wrap items-center gap-2 rounded-lg border border-zinc-800 bg-zinc-950/40 px-3 py-2">
              <label className="text-xs text-zinc-500">
                {t.common.bucket}
                <select
                  value={selectedBucketBySlug[p.slug] ?? "medium"}
                  onChange={(e) =>
                    setSelectedBucketBySlug((prev) => ({
                      ...prev,
                      [p.slug]: e.target.value as Bucket,
                    }))
                  }
                  className="ml-2 rounded-lg border border-zinc-700 bg-zinc-950/80 px-2 py-1 text-xs text-zinc-200"
                >
                  <option value="penny">{t.buckets.penny.label}</option>
                  <option value="medium">{t.buckets.medium.label}</option>
                  <option value="compounder">{t.buckets.compounder.label}</option>
                </select>
              </label>
              <button
                type="button"
                className="btn-ghost px-2 py-1 text-xs hover:bg-zinc-900"
                onClick={async () => {
                  const b = selectedBucketBySlug[p.slug] ?? "medium";
                  try {
                    const preset = await getTraderPreset(p.slug, b);
                    const params = new URLSearchParams();
                    params.set("bucket", b);
                    Object.entries(preset.scan_options).forEach(([k, v]) => {
                      if (v != null) params.set(k, String(v));
                    });
                    setActionMsg(fmt(t.traderIntel.presetReady, { name: p.name, bucket: b }));
                    window.location.href = `/${b}?${params.toString()}`;
                  } catch (err) {
                    setActionMsg(err instanceof Error ? err.message : t.traderIntel.presetFailed);
                  }
                }}
              >
                {t.traderIntel.createStrategy}
              </button>
              <button
                type="button"
                className="btn-primary px-2 py-1 text-xs"
                onClick={async () => {
                  const b = selectedBucketBySlug[p.slug] ?? "medium";
                  try {
                    const compare = await getTraderQuickCompare(p.slug, b);
                    setCompareBySlug((prev) => ({ ...prev, [p.slug]: compare }));
                    setActionMsg(fmt(t.traderIntel.compareComplete, { name: p.name, symbol: compare.symbol }));
                  } catch (err) {
                    setActionMsg(err instanceof Error ? err.message : t.traderIntel.compareFailed);
                  }
                }}
              >
                {t.traderIntel.quickCompare}
              </button>
              <Link href="/library?tab=scans" className="text-xs text-[#7dff8e] underline">
                {t.traderIntel.useSavedScans}
              </Link>
            </div>

            <div className="grid gap-3 lg:grid-cols-2">
              <div>
                <p className="text-xs font-medium text-zinc-300">{t.traderIntel.strategyPrinciples}</p>
                <ul className="mt-1 space-y-1 text-xs text-zinc-500">
                  {p.strategy_principles.map((x) => (
                    <li key={x}>• {x}</li>
                  ))}
                </ul>
              </div>
              <div>
                <p className="text-xs font-medium text-zinc-300">{t.traderIntel.integrationRecipe}</p>
                <p className="mt-1 text-xs text-zinc-500">
                  {t.traderIntel.style}{" "}
                  <span className="text-zinc-300">{p.integration_recipe.style}</span>
                </p>
                <p className="text-xs text-zinc-500">
                  {t.traderIntel.bucketBias}{" "}
                  <span className="text-zinc-300">{p.integration_recipe.bucket_bias.join(", ") || "—"}</span>
                </p>
                <ul className="mt-1 space-y-1 text-xs text-zinc-500">
                  {p.integration_recipe.risk_controls.map((x) => (
                    <li key={x}>• {x}</li>
                  ))}
                </ul>
              </div>
            </div>

            <div>
              <p className="text-xs font-medium text-zinc-300">{t.traderIntel.sources}</p>
              <ul className="mt-1 space-y-1 text-xs">
                {p.sources.map((s) => (
                  <li key={s.url}>
                    <a href={s.url} target="_blank" rel="noreferrer" className="text-[#7dff8e] underline">
                      {s.title}
                    </a>
                    <span className="ml-2 text-zinc-500">({s.source_type})</span>
                  </li>
                ))}
              </ul>
            </div>

            {compareBySlug[p.slug] && (
              <div className="rounded-lg border border-zinc-800 bg-zinc-950/50 p-3">
                <p className="text-xs font-medium text-zinc-300">
                  {fmt(t.traderIntel.compareTitle, {
                    symbol: compareBySlug[p.slug].symbol,
                    bucket: compareBySlug[p.slug].bucket,
                    horizon: compareBySlug[p.slug].horizon,
                  })}
                </p>
                <div className="mt-2 grid gap-3 sm:grid-cols-2">
                  <div className="rounded-lg border border-zinc-800 p-2 text-xs">
                    <p className="font-medium text-zinc-300">{t.traderIntel.baseline}</p>
                    <p className="text-zinc-500">
                      {t.common.return}{" "}
                      {compareBySlug[p.slug].baseline.total_return_pct.toFixed(2)}% · {t.common.sharpe}{" "}
                      {compareBySlug[p.slug].baseline.sharpe_ratio.toFixed(2)}
                    </p>
                    <p className="text-zinc-500">
                      {t.common.hold} {compareBySlug[p.slug].baseline.hold_days}d · {t.common.stop}{" "}
                      {(compareBySlug[p.slug].baseline.stop_pct * 100).toFixed(1)}%
                    </p>
                  </div>
                  <div className="rounded-lg border border-zinc-800 p-2 text-xs">
                    <p className="font-medium text-zinc-300">{t.traderIntel.traderStyle}</p>
                    <p className="text-zinc-500">
                      {t.common.return}{" "}
                      {compareBySlug[p.slug].trader_style.total_return_pct.toFixed(2)}% · {t.common.sharpe}{" "}
                      {compareBySlug[p.slug].trader_style.sharpe_ratio.toFixed(2)}
                    </p>
                    <p className="text-zinc-500">
                      {t.common.hold} {compareBySlug[p.slug].trader_style.hold_days}d · {t.common.stop}{" "}
                      {(compareBySlug[p.slug].trader_style.stop_pct * 100).toFixed(1)}%
                    </p>
                  </div>
                </div>
                <p className="mt-2 text-xs text-zinc-400">
                  {t.traderIntel.deltaReturn}{" "}
                  {compareBySlug[p.slug].delta_total_return_pct.toFixed(2)}% · {t.traderIntel.deltaSharpe}{" "}
                  {compareBySlug[p.slug].delta_sharpe_ratio.toFixed(2)}
                </p>
              </div>
            )}
          </div>
        ))}
      </div>
      {actionMsg && <p className="text-xs text-zinc-500">{actionMsg}</p>}
    </div>
  );
}
