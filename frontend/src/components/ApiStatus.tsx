// Health indicator — pinned footer bar.
"use client";

import { getHealthWithRetry, isApiWakingError } from "@/lib/api";
import { useTranslation } from "@/lib/i18n";
import type { HealthResponse } from "@/lib/types";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

function SourcePill({ label, on, onLabel, offLabel }: { label: string; on?: boolean; onLabel: string; offLabel: string }) {
  return (
    <span className="api-pill api-pill--muted">
      {label}: {on ? onLabel : offLabel}
    </span>
  );
}

export function ApiStatus() {
  const { t } = useTranslation();
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [waking, setWaking] = useState(false);

  const refresh = useCallback(() => {
    setWaking(true);
    getHealthWithRetry()
      .then((data) => {
        setHealth(data);
        setWaking(false);
      })
      .catch((err) => {
        setWaking(isApiWakingError(err));
        setHealth({
          status: "offline",
          alpha_vantage_configured: false,
          fred_configured: false,
          newsapi_configured: false,
        });
      });
  }, []);

  useEffect(() => {
    refresh();
    const onChange = () => refresh();
    window.addEventListener("api-settings-changed", onChange);
    return () => window.removeEventListener("api-settings-changed", onChange);
  }, [refresh]);

  if (!health) {
    return (
      <div className="api-status-bar">
        <span className="text-zinc-600">{t.footer.checking}</span>
      </div>
    );
  }

  const online = health.status === "ok";

  return (
    <div className="api-status-bar">
      {waking && !online && (
        <span className="api-pill api-pill--muted">{t.demo.backendStarting}</span>
      )}
      <span className={online ? "api-pill api-pill--ok" : "api-pill api-pill--bad"}>
        <span
          className={`h-1.5 w-1.5 rounded-full ${online ? "bg-[#00c805]" : "bg-red-400"}`}
          aria-hidden
        />
        {online ? t.footer.apiOnline : t.footer.apiOffline}
      </span>
      {health.demo_mode && (
        <span className="api-pill api-pill--muted">{t.demo.temporaryData}</span>
      )}
      {!health.demo_mode && health.alpha_vantage_configured !== undefined && (
        <>
          <SourcePill label="AV" on={health.alpha_vantage_configured} onLabel={t.footer.on} offLabel={t.footer.off} />
          <SourcePill label="Finnhub" on={health.finnhub_configured} onLabel={t.footer.on} offLabel={t.footer.off} />
          <SourcePill label="FMP" on={health.fmp_configured} onLabel={t.footer.on} offLabel={t.footer.off} />
          <SourcePill label="NDL" on={health.quandl_configured} onLabel={t.footer.on} offLabel={t.footer.off} />
          <SourcePill label="OpenBB" on={health.openbb_enabled} onLabel={t.footer.on} offLabel={t.footer.off} />
          {health.primary_price_source && (
            <span className="api-pill api-pill--muted">
              {health.primary_price_source}/{health.primary_fundamentals_source ?? "—"}
            </span>
          )}
          <SourcePill label="FRED" on={health.fred_configured} onLabel={t.footer.on} offLabel={t.footer.off} />
          <SourcePill label="LLM" on={health.llm_configured} onLabel={t.footer.on} offLabel={t.footer.off} />
        </>
      )}
      {health.scheduler_enabled && (
        <span className="api-pill api-pill--ok">{t.footer.scheduler}</span>
      )}
      {health.strategy_version && (
        <span className="api-pill api-pill--muted" title={t.navAria.pinnedStrategy}>
          {health.strategy_version}
        </span>
      )}
      {!online && (
        <button type="button" className="api-pill api-pill--muted hover:text-zinc-200" onClick={refresh}>
          {t.common.retry}
        </button>
      )}
      <Link href="/settings" className="api-pill api-pill--muted hover:border-[#00c805]/40 hover:text-zinc-300">
        {t.footer.configure}
      </Link>
    </div>
  );
}
