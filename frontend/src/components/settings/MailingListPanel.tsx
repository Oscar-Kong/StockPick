"use client";

import {
  addMailingListSubscriber,
  getMailingList,
  importMailingListFromEnv,
  patchMailingListSubscriber,
  removeMailingListSubscriber,
} from "@/lib/api";
import type { MailingListResponse, MailingListSubscriberItem } from "@/lib/types";
import { fmt, useTranslation } from "@/lib/i18n";
import clsx from "clsx";
import { useCallback, useEffect, useState } from "react";
import { ErrorState } from "@/components/ui/ErrorState";
import { LoadingSkeleton } from "@/components/ui/LoadingSkeleton";
import { PrimaryButton, GhostButton } from "@/components/ui/buttons";

function SourceBadge({ source }: { source: string }) {
  const { t } = useTranslation();
  const label =
    source === "settings"
      ? t.mailingList.sourceSettings
      : source === "env"
        ? t.mailingList.sourceEnv
        : t.mailingList.sourceNone;
  return (
    <span className="rounded bg-zinc-800 px-2 py-0.5 text-xs text-zinc-400">{label}</span>
  );
}

function SubscriberRow({
  item,
  readOnly,
  pending,
  onToggle,
  onRemove,
}: {
  item: MailingListSubscriberItem;
  readOnly: boolean;
  pending: string | null;
  onToggle: (id: string, enabled: boolean) => void;
  onRemove: (id: string) => void;
}) {
  const { t } = useTranslation();
  const busy = pending === item.id;

  return (
    <div className="flex flex-wrap items-center gap-3 border-b border-white/8 px-3 py-2.5 last:border-b-0">
      <div className="min-w-0 flex-1">
        <p className="truncate font-medium text-zinc-100">{item.email}</p>
        {item.label ? <p className="truncate text-xs text-zinc-500">{item.label}</p> : null}
      </div>
      <span
        className={clsx(
          "rounded px-2 py-0.5 text-xs font-medium uppercase tracking-wide",
          item.enabled ? "bg-emerald-950/60 text-emerald-300" : "bg-zinc-800 text-zinc-500"
        )}
      >
        {item.enabled ? t.mailingList.active : t.mailingList.paused}
      </span>
      {!readOnly && (
        <div className="flex items-center gap-2">
          <GhostButton
            type="button"
            disabled={busy}
            className="text-xs"
            onClick={() => onToggle(item.id, !item.enabled)}
          >
            {item.enabled ? t.mailingList.pause : t.mailingList.resume}
          </GhostButton>
          <GhostButton
            type="button"
            disabled={busy}
            className="text-xs text-rose-300 hover:text-rose-200"
            onClick={() => onRemove(item.id)}
          >
            {t.common.remove}
          </GhostButton>
        </div>
      )}
    </div>
  );
}

function notifyMailingListChanged() {
  window.dispatchEvent(new CustomEvent("mailing-list-changed"));
}

export function MailingListPanel() {
  const { t } = useTranslation();
  const [data, setData] = useState<MailingListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [email, setEmail] = useState("");
  const [label, setLabel] = useState("");
  const [pending, setPending] = useState<string | "add" | "import" | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await getMailingList());
    } catch (e) {
      setError(e instanceof Error ? e.message : t.mailingList.loadFailed);
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [t.mailingList.loadFailed]);

  useEffect(() => {
    void load();
  }, [load]);

  const showToast = (message: string) => {
    setToast(message);
    window.setTimeout(() => setToast(null), 5000);
  };

  const onAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = email.trim();
    if (!trimmed) return;
    setPending("add");
    try {
      setData(await addMailingListSubscriber(trimmed, label.trim()));
      setEmail("");
      setLabel("");
      notifyMailingListChanged();
      showToast(t.mailingList.added);
    } catch (err) {
      showToast(err instanceof Error ? err.message : t.mailingList.actionFailed);
    } finally {
      setPending(null);
    }
  };

  const onImportEnv = async () => {
    setPending("import");
    try {
      const res = await importMailingListFromEnv();
      setData(res);
      notifyMailingListChanged();
      showToast(
        res.imported > 0
          ? fmt(t.mailingList.importedCount, { count: String(res.imported) })
          : t.mailingList.importNoneNew
      );
    } catch (err) {
      showToast(err instanceof Error ? err.message : t.mailingList.actionFailed);
    } finally {
      setPending(null);
    }
  };

  const onToggle = async (id: string, enabled: boolean) => {
    setPending(id);
    try {
      setData(await patchMailingListSubscriber(id, { enabled }));
      notifyMailingListChanged();
    } catch (err) {
      showToast(err instanceof Error ? err.message : t.mailingList.actionFailed);
    } finally {
      setPending(null);
    }
  };

  const onRemove = async (id: string) => {
    setPending(id);
    try {
      setData(await removeMailingListSubscriber(id));
      notifyMailingListChanged();
      showToast(t.mailingList.removed);
    } catch (err) {
      showToast(err instanceof Error ? err.message : t.mailingList.actionFailed);
    } finally {
      setPending(null);
    }
  };

  const readOnly = data?.read_only ?? false;

  return (
    <section className="surface-card p-4">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-base font-semibold text-zinc-100">{t.mailingList.title}</h3>
          <p className="mt-1 text-sm text-secondary">{t.mailingList.subtitle}</p>
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

      {loading && <LoadingSkeleton lines={5} />}
      {!loading && error && <ErrorState message={error} onRetry={() => void load()} />}
      {!loading && !error && data && (
        <div className="space-y-4 text-sm">
          <div className="flex flex-wrap items-center gap-2">
            <SourceBadge source={data.recipient_source} />
            <span className="text-xs text-zinc-500">
              {fmt(t.mailingList.recipientSummary, {
                count: String(data.recipient_count),
                active: String(data.active_count),
              })}
            </span>
          </div>

          {readOnly && (
            <p className="rounded-md border border-amber-900/40 bg-amber-950/20 px-3 py-2 text-amber-200">
              {t.mailingList.demoReadOnly}
            </p>
          )}

          {!readOnly && (
            <form onSubmit={(e) => void onAdd(e)} className="grid gap-2 sm:grid-cols-[1fr_1fr_auto]">
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder={t.mailingList.emailPlaceholder}
                className="input-field text-sm"
              />
              <input
                type="text"
                value={label}
                onChange={(e) => setLabel(e.target.value)}
                placeholder={t.mailingList.labelPlaceholder}
                className="input-field text-sm"
              />
              <PrimaryButton type="submit" disabled={pending === "add"}>
                {pending === "add" ? t.common.loading : t.mailingList.addEmail}
              </PrimaryButton>
            </form>
          )}

          {!readOnly && data.recipient_source === "env" && (
            <div className="flex flex-wrap items-center gap-2 rounded-md border border-white/8 bg-zinc-900/40 px-3 py-2">
              <p className="text-xs text-zinc-400">{t.mailingList.envFallbackHint}</p>
              <GhostButton
                type="button"
                disabled={pending === "import"}
                className="text-xs"
                onClick={() => void onImportEnv()}
              >
                {pending === "import" ? t.common.loading : t.mailingList.importFromEnv}
              </GhostButton>
            </div>
          )}

          {data.subscribers.length === 0 ? (
            <p className="rounded-md border border-dashed border-white/10 px-3 py-4 text-center text-zinc-500">
              {t.mailingList.empty}
            </p>
          ) : (
            <div className="overflow-hidden rounded-md border border-white/8">
              {data.subscribers.map((item) => (
                <SubscriberRow
                  key={item.id}
                  item={item}
                  readOnly={readOnly}
                  pending={pending}
                  onToggle={(id, enabled) => void onToggle(id, enabled)}
                  onRemove={(id) => void onRemove(id)}
                />
              ))}
            </div>
          )}

          <p className="text-xs text-zinc-500">{t.mailingList.smtpNote}</p>
        </div>
      )}
    </section>
  );
}
