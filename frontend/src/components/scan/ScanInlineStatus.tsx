"use client";

import { StrategyVersionBadge } from "@/components/DataQualityBadge";
import { ScoreSourceBadge } from "@/components/ScoreSourceBadge";
import { StaleDataBadge } from "@/components/badges/StaleDataBadge";
import { formatDateTime } from "@/lib/datetime";
import { fmt, useTranslation } from "@/lib/i18n";
import type { ScanParitySummary } from "@/lib/types";
import type { ScoreSource } from "@/lib/v2Score";
import clsx from "clsx";
import { useState } from "react";

interface ScanInlineStatusProps {
  status: string;
  scanning: boolean;
  progress: number;
  message: string;
  lastScanAt?: string | null;
  strategyVersion?: string | null;
  scoringEngineUsed?: boolean | null;
  paritySummary?: ScanParitySummary | null;
  scanStale?: boolean;
  resultCount?: number;
}

export function ScanInlineStatus({
  status,
  scanning,
  progress,
  message,
  lastScanAt,
  strategyVersion,
  scoringEngineUsed,
  paritySummary,
  scanStale,
  resultCount = 0,
}: ScanInlineStatusProps) {
  const { t } = useTranslation();
  const [detailsOpen, setDetailsOpen] = useState(false);

  const source: ScoreSource | null =
    scoringEngineUsed == null ? null : scoringEngineUsed ? "scoring_engine_v2" : "legacy_screener";

  const hasParity =
    paritySummary != null &&
    (paritySummary.average_delta != null || paritySummary.max_delta != null);

  const stateLabel =
    scanning || status === "running"
      ? resultCount > 0
        ? t.scan.statusPartial
        : t.scan.statusRunning
      : status === "failed"
        ? t.scan.statusFailed
        : status === "completed"
          ? resultCount > 0
            ? t.scan.statusCompleted
            : t.scan.statusEmpty
          : t.scan.statusIdle;

  return (
    <div className="scan-inline-status">
      <div className="scan-inline-status__row">
        <span
          className={clsx(
            "scan-inline-status__state",
            (scanning || status === "running") && "scan-inline-status__state--running",
            status === "failed" && "scan-inline-status__state--failed",
            status === "completed" && resultCount === 0 && "scan-inline-status__state--empty",
            (scanning || status === "running") && resultCount > 0 && "scan-inline-status__state--partial"
          )}
        >
          {stateLabel}
        </span>
        {(scanning || status === "running") && (
          <span className="scan-inline-status__progress finance-value">{Math.round(progress)}%</span>
        )}
        {message && (scanning || status === "running") && (
          <span className="scan-inline-status__message truncate">{message}</span>
        )}
        {status === "failed" && message && (
          <span className="scan-inline-status__failure" role="alert" title={message}>
            {message}
          </span>
        )}
        <span className="scan-inline-status__sep" aria-hidden>
          ·
        </span>
        <span className="scan-inline-status__item">
          {t.scan.lastScanLabel}{" "}
          <span className="finance-value text-secondary">
            {lastScanAt ? formatDateTime(lastScanAt) : "—"}
          </span>
        </span>
        <span className="scan-inline-status__sep" aria-hidden>
          ·
        </span>
        <span className="scan-inline-status__item">
          {t.scan.resultCountLabel}{" "}
          <span className="finance-value text-foreground">{resultCount > 0 ? resultCount : "—"}</span>
        </span>
        {lastScanAt && (
          <>
            <span className="scan-inline-status__sep" aria-hidden>
              ·
            </span>
            {scanStale ? (
              <StaleDataBadge asOf={lastScanAt} />
            ) : (
              <span className="text-sm text-positive">{t.product.dataFresh}</span>
            )}
          </>
        )}
        {source && (
          <>
            <span className="scan-inline-status__sep hidden sm:inline" aria-hidden>
              ·
            </span>
            <span className="hidden sm:inline">
              <ScoreSourceBadge source={source} />
            </span>
          </>
        )}
        {strategyVersion && (
          <span className="hidden md:inline">
            <StrategyVersionBadge version={strategyVersion} />
          </span>
        )}
        <button
          type="button"
          className="scan-inline-status__details-btn"
          onClick={() => setDetailsOpen((o) => !o)}
          aria-expanded={detailsOpen}
        >
          {t.scan.statusDetails}
        </button>
      </div>
      {detailsOpen && (
        <div className="scan-inline-status__details">
          {hasParity && (
            <p className="text-sm text-secondary">
              {fmt(t.scan.parityDetail, {
                avg: paritySummary?.average_delta?.toFixed(1) ?? "—",
                max: paritySummary?.max_delta?.toFixed(1) ?? "—",
                diffs: String(paritySummary?.recommendation_bucket_diffs ?? 0),
              })}
            </p>
          )}
          {!hasParity && <p className="text-sm text-secondary">{t.product.parityUnavailable}</p>}
        </div>
      )}
    </div>
  );
}

export function ScanProgressBar({ progress, message }: { progress: number; message: string }) {
  return (
    <div className="scan-progress-bar">
      <div className="scan-progress-bar__track" role="progressbar" aria-valuenow={progress} aria-valuemin={0} aria-valuemax={100}>
        <div className="scan-progress-bar__fill" style={{ width: `${Math.min(100, Math.max(0, progress))}%` }} />
      </div>
      {message && <p className="scan-progress-bar__message">{message}</p>}
    </div>
  );
}
