"use client";

import { useCallback, useEffect, useState } from "react";
import clsx from "clsx";
import { getActivePositionMonitor, runActivePositionMonitor } from "@/lib/api/portfolio";
import type { ActivePositionMonitorResponse, ActivePositionState, ActivePositionStatus } from "@/lib/types";
import { useTranslation } from "@/lib/i18n";
import { SectionCard } from "@/components/ui/AppCard";
import { SecondaryButton } from "@/components/ui/buttons";
import { ErrorState } from "@/components/ui/ErrorState";
import { LoadingSkeleton } from "@/components/ui/LoadingSkeleton";

const POLL_INTERVAL_MS = 60_000;

function formatPct(value?: number | null) {
  if (value == null || !Number.isFinite(value)) return "—";
  return `${value >= 0 ? "+" : ""}${value.toFixed(1)}%`;
}

function formatPrice(value?: number | null) {
  if (value == null || !Number.isFinite(value)) return "—";
  return `$${value.toFixed(value < 10 ? 3 : 2)}`;
}

function stateTone(state: ActivePositionState) {
  if (state === "EXIT" || state === "EXIT_WARNING") return "signal-sell";
  if (state === "TRIM" || state === "DATA_STALE" || state === "ADD_SETUP") return "signal-hold";
  if (state === "ADD_CONFIRMED") return "signal-buy";
  return "bg-[var(--color-primary-subtle)] text-primary";
}

export function ActivePositionMonitorPanel() {
  const { t, locale } = useTranslation();
  const [data, setData] = useState<ActivePositionMonitorResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const stateLabel = useCallback(
    (state: ActivePositionState) => {
      const labels: Record<ActivePositionState, string> = {
        HOLD: t.portfolio.activeMonitorStateHold,
        ADD_SETUP: t.portfolio.activeMonitorStateAddSetup,
        ADD_CONFIRMED: t.portfolio.activeMonitorStateAddConfirmed,
        TRIM: t.portfolio.activeMonitorStateTrim,
        EXIT_WARNING: t.portfolio.activeMonitorStateExitWarning,
        EXIT: t.portfolio.activeMonitorStateExit,
        DATA_STALE: t.portfolio.activeMonitorStateDataStale,
      };
      return labels[state];
    },
    [t],
  );

  const load = useCallback(async () => {
    try {
      const result = await getActivePositionMonitor();
      setData(result);
      setError(null);
    } catch {
      setError(t.portfolio.activeMonitorLoadFailed);
    } finally {
      setLoading(false);
    }
  }, [t.portfolio.activeMonitorLoadFailed]);

  useEffect(() => {
    void load();
    const timer = window.setInterval(() => void load(), POLL_INTERVAL_MS);
    return () => window.clearInterval(timer);
  }, [load]);

  const refresh = async () => {
    setRefreshing(true);
    try {
      setData(await runActivePositionMonitor(true));
      setError(null);
    } catch {
      setError(t.portfolio.activeMonitorLoadFailed);
    } finally {
      setRefreshing(false);
      setLoading(false);
    }
  };

  const quoteTime = data?.quote_as_of
    ? new Intl.DateTimeFormat(locale === "zh" ? "zh-CN" : "en-US", {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      }).format(new Date(data.quote_as_of))
    : null;

  return (
    <SectionCard
      title={t.portfolio.activeMonitorTitle}
      subtitle={t.portfolio.activeMonitorSubtitle}
      variant="elevated"
      action={
        <SecondaryButton size="sm" onClick={refresh} disabled={refreshing}>
          {refreshing ? t.portfolio.activeMonitorRefreshing : t.portfolio.activeMonitorRefresh}
        </SecondaryButton>
      }
    >
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2 text-xs text-secondary">
        <span>{t.portfolio.activeMonitorReadOnly}</span>
        {quoteTime && <span>{t.portfolio.activeMonitorLastQuote.replace("{time}", quoteTime)}</span>}
      </div>

      {loading && !data ? (
        <LoadingSkeleton lines={4} />
      ) : error && !data ? (
        <ErrorState message={error} onRetry={() => void load()} />
      ) : !data?.statuses.length ? (
        <p className="rounded-lg border border-[var(--color-border)] px-4 py-6 text-center text-sm text-secondary">
          {t.portfolio.activeMonitorEmpty}
        </p>
      ) : (
        <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
          {data.statuses.map((position) => (
            <PositionStatusCard key={position.symbol} position={position} stateLabel={stateLabel} />
          ))}
        </div>
      )}
      {error && data && <ErrorState className="mt-3" message={error} onRetry={() => void load()} />}
    </SectionCard>
  );
}

function PositionStatusCard({
  position,
  stateLabel,
}: {
  position: ActivePositionStatus;
  stateLabel: (state: ActivePositionState) => string;
}) {
  const { t } = useTranslation();
  const fresh = position.data_status === "fresh";
  return (
    <article className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-mono text-sm font-semibold text-[var(--color-foreground)]">{position.symbol}</h3>
          <p className={clsx("mt-0.5 text-xs", fresh ? "text-[var(--color-buy)]" : "text-[var(--color-hold)]")}>
            {fresh ? t.portfolio.activeMonitorFresh : t.portfolio.activeMonitorStale}
          </p>
        </div>
        <span className={clsx("badge", stateTone(position.state))}>{stateLabel(position.state)}</span>
      </div>
      <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 text-xs tabular-nums">
        <Metric label={t.portfolio.activeMonitorPrice} value={formatPrice(position.price)} />
        <Metric
          label={t.portfolio.activeMonitorPl}
          value={formatPct(position.unrealized_pl_pct)}
          tone={(position.unrealized_pl_pct ?? 0) >= 0 ? "positive" : "negative"}
        />
        <Metric label={t.portfolio.activeMonitorStopDistance} value={formatPct(position.distance_to_stop_pct)} />
        <Metric label={t.portfolio.activeMonitorTargetDistance} value={formatPct(position.distance_to_target_pct)} />
      </dl>
      {position.evidence[0] && <p className="mt-3 border-t border-[var(--color-divider)] pt-2 text-xs leading-relaxed text-secondary">{position.evidence[0]}</p>}
    </article>
  );
}

function Metric({ label, value, tone }: { label: string; value: string; tone?: "positive" | "negative" }) {
  return (
    <div>
      <dt className="text-[var(--color-foreground-muted)]">{label}</dt>
      <dd
        className={clsx(
          "mt-0.5 text-sm font-medium text-[var(--color-foreground)]",
          tone === "positive" && "text-[var(--color-buy)]",
          tone === "negative" && "text-[var(--color-sell)]",
        )}
      >
        {value}
      </dd>
    </div>
  );
}
