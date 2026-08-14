"use client";

import {
  getMorningScanEmailStatus,
  previewMorningScanEmail,
  sendMorningScanEmailTest,
  updateMorningScanEmailSettings,
} from "@/lib/api";
import type { MorningScanEmailSendResponse, MorningScanEmailStatusResponse } from "@/lib/types";
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
  const [actionPending, setActionPending] = useState<"test" | "preview" | "save" | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const [sendTime, setSendTime] = useState("09:20");
  const [staleMinutes, setStaleMinutes] = useState(1440);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewSubject, setPreviewSubject] = useState("");
  const [previewIntro, setPreviewIntro] = useState("");
  const [previewResult, setPreviewResult] = useState<MorningScanEmailSendResponse | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const next = await getMorningScanEmailStatus();
      setStatus(next);
      setSendTime(next.send_time_et || "09:20");
      setStaleMinutes(next.stale_after_minutes ?? 1440);
      setPreviewSubject(next.subject_template || "");
      setPreviewIntro(next.intro_note || "");
    } catch (e) {
      setError(e instanceof Error ? e.message : t.morningScanEmail.loadFailed);
      setStatus(null);
    } finally {
      setLoading(false);
    }
  }, [t.morningScanEmail.loadFailed]);

  useEffect(() => {
    void load();
    const onMailingListChanged = () => void load();
    window.addEventListener("mailing-list-changed", onMailingListChanged);
    return () => window.removeEventListener("mailing-list-changed", onMailingListChanged);
  }, [load]);

  const showToast = (message: string) => {
    setToast(message);
    window.setTimeout(() => setToast(null), 5000);
  };

  const onSaveSchedule = async () => {
    setActionPending("save");
    try {
      const next = await updateMorningScanEmailSettings({
        send_time_et: sendTime,
        stale_after_minutes: staleMinutes,
      });
      setStatus(next);
      setSendTime(next.send_time_et || sendTime);
      setStaleMinutes(next.stale_after_minutes ?? staleMinutes);
      showToast(t.morningScanEmail.settingsSaved);
    } catch (e) {
      showToast(e instanceof Error ? e.message : t.morningScanEmail.actionFailed);
    } finally {
      setActionPending(null);
    }
  };

  const onOpenPreview = async () => {
    setActionPending("preview");
    try {
      const res = await previewMorningScanEmail({
        subject_template: previewSubject || null,
        intro_note: previewIntro || null,
      });
      setPreviewResult(res);
      setPreviewOpen(true);
      showToast(res.message || t.morningScanEmail.previewOk);
    } catch (e) {
      showToast(e instanceof Error ? e.message : t.morningScanEmail.actionFailed);
    } finally {
      setActionPending(null);
    }
  };

  const onRefreshPreview = async () => {
    setActionPending("preview");
    try {
      const res = await previewMorningScanEmail({
        subject_template: previewSubject || null,
        intro_note: previewIntro || null,
      });
      setPreviewResult(res);
      showToast(t.morningScanEmail.previewRefreshed);
    } catch (e) {
      showToast(e instanceof Error ? e.message : t.morningScanEmail.actionFailed);
    } finally {
      setActionPending(null);
    }
  };

  const onSavePreviewCopy = async () => {
    setActionPending("save");
    try {
      const next = await updateMorningScanEmailSettings({
        subject_template: previewSubject,
        intro_note: previewIntro,
        clear_subject_template: !previewSubject.trim(),
        clear_intro_note: !previewIntro.trim(),
      });
      setStatus(next);
      setPreviewSubject(next.subject_template || "");
      setPreviewIntro(next.intro_note || "");
      showToast(t.morningScanEmail.previewSaved);
      const res = await previewMorningScanEmail({
        subject_template: next.subject_template,
        intro_note: next.intro_note,
      });
      setPreviewResult(res);
    } catch (e) {
      showToast(e instanceof Error ? e.message : t.morningScanEmail.actionFailed);
    } finally {
      setActionPending(null);
    }
  };

  const onTestSend = async () => {
    setActionPending("test");
    try {
      const res = await sendMorningScanEmailTest({
        subject_template: previewSubject || null,
        intro_note: previewIntro || null,
      });
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

          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block space-y-1">
              <span className="text-xs uppercase tracking-wide text-zinc-500">
                {t.morningScanEmail.sendTime}
              </span>
              <input
                type="time"
                value={sendTime}
                onChange={(e) => setSendTime(e.target.value)}
                className="w-full rounded-md border border-zinc-700 bg-zinc-950 px-3 py-2 text-zinc-100"
                aria-describedby="morning-scan-send-time-hint"
              />
              <span id="morning-scan-send-time-hint" className="block text-xs text-zinc-500">
                {t.morningScanEmail.sendTimeHint}
              </span>
            </label>
            <label className="block space-y-1">
              <span className="text-xs uppercase tracking-wide text-zinc-500">
                {t.morningScanEmail.freshnessMinutes}
              </span>
              <input
                type="number"
                min={1}
                max={10080}
                value={staleMinutes}
                onChange={(e) => setStaleMinutes(Number(e.target.value) || 1)}
                className="w-full rounded-md border border-zinc-700 bg-zinc-950 px-3 py-2 text-zinc-100"
                aria-describedby="morning-scan-freshness-hint"
              />
              <span id="morning-scan-freshness-hint" className="block text-xs text-zinc-500">
                {t.morningScanEmail.freshnessHint}
              </span>
            </label>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <PrimaryButton
              type="button"
              disabled={!!actionPending}
              onClick={() => void onSaveSchedule()}
            >
              {actionPending === "save" ? t.common.loading : t.morningScanEmail.saveSchedule}
            </PrimaryButton>
            <span className="text-xs text-zinc-500">
              {fmt(t.morningScanEmail.scheduleSummary, { label: status.schedule_label })}
            </span>
          </div>

          <dl className="grid gap-2 sm:grid-cols-2">
            <div>
              <dt className="text-xs uppercase tracking-wide text-zinc-500">{t.morningScanEmail.provider}</dt>
              <dd className="text-zinc-200">{status.provider}</dd>
            </div>
            <div className="sm:col-span-2">
              <dt className="text-xs uppercase tracking-wide text-zinc-500">{t.morningScanEmail.recipient}</dt>
              <dd className="text-zinc-200">
                {status.recipients.length > 0
                  ? status.recipients.join(", ")
                  : status.recipient_masked}
              </dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-zinc-500">
                {t.morningScanEmail.recipientSource}
              </dt>
              <dd className="text-zinc-200">
                {status.recipient_source === "settings"
                  ? t.morningScanEmail.sourceSettings
                  : status.recipient_source === "env"
                    ? t.morningScanEmail.sourceEnv
                    : t.morningScanEmail.sourceNone}
              </dd>
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
            {status.recipients.length > 0 ? (
              <p className="w-full text-xs text-zinc-400">
                {t.morningScanEmail.testSendHint} {status.recipients.join(", ")}
              </p>
            ) : (
              <p className="w-full text-xs text-amber-300">{t.morningScanEmail.noRecipientsConfigured}</p>
            )}
            <PrimaryButton
              type="button"
              disabled={!!actionPending || !status.configured}
              onClick={() => void onOpenPreview()}
            >
              {actionPending === "preview" ? t.common.loading : t.morningScanEmail.preview}
            </PrimaryButton>
            <GhostButton
              type="button"
              disabled={!!actionPending || !status.configured || status.recipients.length === 0}
              onClick={() => void onTestSend()}
            >
              {actionPending === "test" ? t.common.loading : t.morningScanEmail.sendTest}
            </GhostButton>
          </div>
        </div>
      )}

      {previewOpen && (
        <div
          className="fixed inset-0 z-50 flex items-end justify-center bg-black/70 p-3 sm:items-center"
          role="dialog"
          aria-modal="true"
          aria-labelledby="morning-scan-preview-title"
          onClick={() => setPreviewOpen(false)}
        >
          <div
            className="flex max-h-[90vh] w-full max-w-3xl flex-col overflow-hidden rounded-lg border border-zinc-700 bg-zinc-950 shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-3 border-b border-zinc-800 px-4 py-3">
              <div>
                <h4 id="morning-scan-preview-title" className="text-base font-semibold text-zinc-100">
                  {t.morningScanEmail.previewEditorTitle}
                </h4>
                <p className="mt-1 text-xs text-zinc-500">{t.morningScanEmail.previewEditorHint}</p>
              </div>
              <GhostButton type="button" className="text-xs" onClick={() => setPreviewOpen(false)}>
                {t.common.close}
              </GhostButton>
            </div>
            <div className="space-y-3 overflow-y-auto px-4 py-3">
              <label className="block space-y-1">
                <span className="text-xs uppercase tracking-wide text-zinc-500">
                  {t.morningScanEmail.subjectTemplate}
                </span>
                <input
                  type="text"
                  value={previewSubject}
                  onChange={(e) => setPreviewSubject(e.target.value)}
                  placeholder={t.morningScanEmail.subjectPlaceholder}
                  className="w-full rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100"
                  maxLength={200}
                />
              </label>
              <label className="block space-y-1">
                <span className="text-xs uppercase tracking-wide text-zinc-500">
                  {t.morningScanEmail.introNote}
                </span>
                <textarea
                  value={previewIntro}
                  onChange={(e) => setPreviewIntro(e.target.value)}
                  placeholder={t.morningScanEmail.introPlaceholder}
                  rows={3}
                  maxLength={2000}
                  className="w-full rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100"
                />
              </label>
              {previewResult?.subject && (
                <p className="text-xs text-zinc-400">
                  {t.morningScanEmail.renderedSubject}:{" "}
                  <span className="text-zinc-200">{previewResult.subject}</span>
                </p>
              )}
              <div className="overflow-hidden rounded-md border border-zinc-800 bg-white">
                {previewResult?.html_preview ? (
                  <iframe
                    title={t.morningScanEmail.previewFrameTitle}
                    srcDoc={previewResult.html_preview}
                    className="h-[50vh] w-full bg-white"
                    sandbox=""
                  />
                ) : (
                  <p className="p-4 text-sm text-zinc-600">{t.morningScanEmail.previewEmpty}</p>
                )}
              </div>
            </div>
            <div className="flex flex-wrap gap-2 border-t border-zinc-800 px-4 py-3">
              <GhostButton
                type="button"
                disabled={!!actionPending}
                onClick={() => void onRefreshPreview()}
              >
                {t.morningScanEmail.refreshPreview}
              </GhostButton>
              <PrimaryButton
                type="button"
                disabled={!!actionPending}
                onClick={() => void onSavePreviewCopy()}
              >
                {t.morningScanEmail.savePreviewCopy}
              </PrimaryButton>
              <GhostButton
                type="button"
                disabled={!!actionPending || !status?.configured || (status?.recipients.length ?? 0) === 0}
                onClick={() => void onTestSend()}
              >
                {t.morningScanEmail.sendTest}
              </GhostButton>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
