"use client";

import {
  getMorningScanEmailStatus,
  previewMorningScanEmail,
  sendMorningScanEmailTest,
} from "@/lib/api";
import type { MorningScanEmailStatusResponse } from "@/lib/types";
import { fmt, useTranslation } from "@/lib/i18n";
import clsx from "clsx";
import { useCallback, useEffect, useState } from "react";
import { ErrorState } from "@/components/ui/ErrorState";
import { LoadingSkeleton } from "@/components/ui/LoadingSkeleton";
import { PrimaryButton, GhostButton } from "@/components/ui/buttons";

function StatusBadge({ active, label }: { active: boolean; label: string }) {
  return (
    <span
      className={clsx(
        "rounded px-2 py-0.5 text-xs font-medium uppercase tracking-wide",
        active ? "bg-emerald-950/60 text-emerald-300" : "bg-zinc-800 text-zinc-500"
      )}
    >
      {label}
    </span>
  );
}

export function MorningScanEmailPanel() {
  const { t } = useTranslation();
  const [status, setStatus] = useState<MorningScanEmailStatusResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionPending, setActionPending] = useState<"test" | "preview" | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setStatus(await getMorningScanEmailStatus());
    } catch (e) {
      setError(e instanceof Error ? e.message : t.morningScanEmail.loadFailed);
      setStatus(null);
    } finally {
      setLoading(false);
    }
  }, [t.morningScanEmail.loadFailed]);

  useEffect(() => {
    void load();
  }, [load]);

  const showToast = (message: string) => {
    setToast(message);
    window.setTimeout(() => setToast(null), 5000);
  };

  const onPreview = async () => {
    setActionPending("preview");
    try {
      const res = await previewMorningScanEmail();
      showToast(res.message || t.morningScanEmail.previewOk);
    } catch (e) {
      showToast(e instanceof Error ? e.message : t.morningScanEmail.actionFailed);
    } finally {
      setActionPending(null);
    }
  };

  const onTestSend = async () => {
    setActionPending("test");
    try {
      const res = await sendMorningScanEmailTest();
      showToast(res.message || t.morningScanEmail.testOk);
      await load();
    } catch (e) {
      showToast(e instanceof Error ? e.message : t.morningScanEmail.actionFailed);
    } finally {
      setActionPending(null);
    }
  };

  return (
    <section className="surface-card p-4">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-base font-semibold text-zinc-100">{t.morningScanEmail.title}</h3>
          <p className="mt-1 text-sm text-secondary">{t.morningScanEmail.subtitle}</p>
        </div>
        <GhostButton type="button" onClick={() => void load()} disabled={loading} className="text-xs">
          {t.common.refresh}
        </GhostButton>
      </div>

      {toast && (
        <p className="mb-3 rounded-md border border-emerald-900/50 bg-emerald-950/30 px-3 py-2 text-sm text-emerald-200">
          {toast}
        </p>
      )}

      {loading && <LoadingSkeleton lines={6} />}
      {!loading && error && <ErrorState message={error} onRetry={() => void load()} />}
      {!loading && !error && status && (
        <div className="space-y-4 text-sm">
          <div className="flex flex-wrap gap-2">
            <StatusBadge
              active={status.enabled}
              label={status.enabled ? t.morningScanEmail.enabled : t.morningScanEmail.disabled}
            />
            <StatusBadge
              active={status.scheduler_active}
              label={
                status.scheduler_active
                  ? t.morningScanEmail.schedulerActive
                  : t.morningScanEmail.schedulerInactive
              }
            />
            <span className="rounded bg-zinc-800 px-2 py-0.5 text-xs text-zinc-400">
              {t.morningScanEmail.envControlled}
            </span>
          </div>

          <dl className="grid gap-2 sm:grid-cols-2">
            <div>
              <dt className="text-xs uppercase tracking-wide text-zinc-500">{t.morningScanEmail.provider}</dt>
              <dd className="text-zinc-200">{status.provider}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-zinc-500">{t.morningScanEmail.recipient}</dt>
              <dd className="text-zinc-200">{status.recipient_masked}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-zinc-500">{t.morningScanEmail.schedule}</dt>
              <dd className="text-zinc-200">{status.schedule_label}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-zinc-500">{t.morningScanEmail.buckets}</dt>
              <dd className="text-zinc-200">{status.buckets.join(", ") || "—"}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-zinc-500">{t.morningScanEmail.nextRun}</dt>
              <dd className="text-zinc-200">{status.next_run_at ?? "—"}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-zinc-500">{t.morningScanEmail.lastSuccess}</dt>
              <dd className="text-zinc-200">
                {status.last_successful_delivery?.sent_at ?? "—"}
              </dd>
            </div>
            <div className="sm:col-span-2">
              <dt className="text-xs uppercase tracking-wide text-zinc-500">{t.morningScanEmail.lastAttempt}</dt>
              <dd className="text-zinc-200">
                {status.last_attempted_delivery
                  ? fmt("{status} — {at}", {
                      status: status.last_attempted_delivery.status,
                      at: status.last_attempted_delivery.created_at ?? "—",
                    })
                  : "—"}
              </dd>
            </div>
            {status.last_attempted_delivery?.error_summary && (
              <div className="sm:col-span-2">
                <dt className="text-xs uppercase tracking-wide text-zinc-500">{t.morningScanEmail.lastError}</dt>
                <dd className="text-amber-200">{status.last_attempted_delivery.error_summary}</dd>
              </div>
            )}
          </dl>

          {status.config_errors.length > 0 && (
            <div className="rounded-md border border-amber-900/50 bg-amber-950/20 px-3 py-2 text-amber-200">
              <p className="text-xs font-medium uppercase tracking-wide">{t.morningScanEmail.configErrors}</p>
              <ul className="mt-1 list-inside list-disc text-sm">
                {status.config_errors.map((msg) => (
                  <li key={msg}>{msg}</li>
                ))}
              </ul>
            </div>
          )}

          <div className="flex flex-wrap gap-2 pt-2">
            <PrimaryButton
              type="button"
              disabled={!!actionPending || !status.configured}
              onClick={() => void onPreview()}
            >
              {actionPending === "preview" ? t.common.loading : t.morningScanEmail.preview}
            </PrimaryButton>
            <GhostButton
              type="button"
              disabled={!!actionPending || !status.enabled}
              onClick={() => void onTestSend()}
            >
              {actionPending === "test" ? t.common.loading : t.morningScanEmail.sendTest}
            </GhostButton>
          </div>
        </div>
      )}
    </section>
  );
}
