"use client";

import { getApiSettings, patchApiSettings, resetApiSettings } from "@/lib/api";
import { fmt, useTranslation } from "@/lib/i18n";
import type { ApiSettingsResponse, ApiSettingItem } from "@/lib/types";
import clsx from "clsx";
import { useCallback, useEffect, useState } from "react";

function notifySettingsChanged() {
  window.dispatchEvent(new CustomEvent("api-settings-changed"));
}

function Toggle({
  checked,
  disabled,
  onChange,
  label,
}: {
  checked: boolean;
  disabled?: boolean;
  onChange: (next: boolean) => void;
  label: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={clsx(
        "inline-flex h-7 w-12 shrink-0 items-center rounded-full p-0.5 transition-colors",
        checked ? "justify-end bg-[#00c805]/80" : "justify-start bg-zinc-700",
        disabled ? "cursor-not-allowed opacity-50" : "cursor-pointer"
      )}
    >
      <span className="block h-5 w-5 rounded-full bg-white shadow-md ring-1 ring-black/10" />
    </button>
  );
}

function SettingRow({
  item,
  pending,
  onToggle,
}: {
  item: ApiSettingItem;
  pending: boolean;
  onToggle: (key: string, enabled: boolean) => void;
}) {
  const { t } = useTranslation();
  const needsKey = item.requires_key != null;
  const missingKey = needsKey && item.configured === false;
  const active = item.enabled && !missingKey;

  return (
    <div className="flex items-center gap-4 border-b border-zinc-800/80 px-4 py-3.5 last:border-b-0">
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-medium text-zinc-100">{item.label}</span>
          {item.overridden && (
            <span className="rounded bg-amber-950/50 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-amber-300">
              {t.settings.overridden}
            </span>
          )}
          {needsKey && (
            <span
              className={clsx(
                "rounded px-1.5 py-0.5 text-[10px] uppercase tracking-wide",
                item.configured ? "bg-emerald-950/50 text-emerald-300" : "bg-zinc-800 text-zinc-500"
              )}
            >
              {item.configured ? t.settings.keySet : t.settings.noKey}
            </span>
          )}
          {!needsKey && active && (
            <span className="rounded bg-emerald-950/50 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-emerald-300">
              {t.settings.active}
            </span>
          )}
        </div>
        <p className="mt-1 text-xs leading-relaxed text-zinc-500">{item.description}</p>
        {missingKey && item.enabled && (
          <p className="mt-1 text-xs text-amber-400/90">
            {fmt(t.settings.addKeyHint, { key: item.requires_key ?? "" })}
          </p>
        )}
      </div>
      <div className="flex w-12 shrink-0 items-center justify-center">
        <Toggle
          label={fmt(t.settings.toggleLabel, { label: item.label })}
          checked={item.enabled}
          disabled={pending}
          onChange={(next) => onToggle(item.key, next)}
        />
      </div>
    </div>
  );
}

export function ApiSettingsPanel() {
  const { t } = useTranslation();
  const [data, setData] = useState<ApiSettingsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pendingKey, setPendingKey] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const res = await getApiSettings();
      setData(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : t.settings.loadFailed);
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    void load();
  }, [load]);

  const handleToggle = async (key: string, enabled: boolean) => {
    setPendingKey(key);
    setMessage(null);
    try {
      const res = await patchApiSettings({ [key]: enabled });
      setData(res);
      const name = key.replace(/_ENABLED$/, "").replace(/_/g, " ");
      setMessage(
        fmt(t.settings.toggleOnOff, {
          name,
          state: enabled ? t.footer.on : t.footer.off,
        })
      );
      notifySettingsChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : t.settings.updateFailed);
    } finally {
      setPendingKey(null);
    }
  };

  const handleResetAll = async () => {
    setPendingKey("*");
    setMessage(null);
    try {
      const res = await resetApiSettings();
      setData(res);
      setMessage(t.settings.resetMessage);
      notifySettingsChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : t.settings.resetFailed);
    } finally {
      setPendingKey(null);
    }
  };

  if (loading) {
    return (
      <div className="surface-card p-8 text-center text-sm text-zinc-500">{t.settings.loadingApi}</div>
    );
  }

  if (error && !data) {
    return (
      <div className="surface-card border-red-900/50 p-8 text-center text-sm text-red-300">{error}</div>
    );
  }

  if (!data) return null;

  return (
    <div className="space-y-6">
      <div className="surface-card p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold text-zinc-100">{t.settings.activeRouting}</h2>
            <p className="mt-1 text-xs text-zinc-500">
              {fmt(t.settings.routingDetail, {
                price: data.primary_price_source,
                fundamentals: data.primary_fundamentals_source,
                news: data.primary_news_source,
              })}
            </p>
          </div>
          <button
            type="button"
            onClick={() => void handleResetAll()}
            disabled={pendingKey !== null}
            className="rounded-lg border border-zinc-700 px-3 py-1.5 text-xs text-zinc-400 transition hover:border-zinc-500 hover:text-zinc-200 disabled:opacity-50"
          >
            {t.settings.resetDefaults}
          </button>
        </div>
        {message && <p className="mt-3 text-xs text-[#7dff8e]">{message}</p>}
        {error && <p className="mt-3 text-xs text-red-400">{error}</p>}
        <p className="mt-3 text-xs text-zinc-600">{t.settings.togglesHint}</p>
      </div>

      {data.groups.map((group) => (
        <section key={group.id} className="surface-card overflow-hidden">
          <div className="border-b border-zinc-800 px-4 py-3">
            <h3 className="text-sm font-semibold text-zinc-100">{group.title}</h3>
            <p className="mt-0.5 text-xs text-zinc-500">{group.description}</p>
          </div>
          <div>
            {group.items.map((item) => (
              <SettingRow
                key={item.key}
                item={item}
                pending={pendingKey !== null}
                onToggle={handleToggle}
              />
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
