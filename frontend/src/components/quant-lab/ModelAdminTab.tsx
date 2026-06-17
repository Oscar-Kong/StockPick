"use client";

import {
  getV2Audit,
  getV2FactorsAdmin,
  getV2SleeveWeights,
  getV2Version,
} from "@/lib/api";
import { isFeatureDisabledError, parseApiError } from "@/lib/apiError";
import type { V2FactorsAdminResponse } from "@/lib/types";
import { useTranslation } from "@/lib/i18n";
import { useCallback, useEffect, useMemo, useState } from "react";
import { computeModelAdminReliability } from "@/lib/researchReliability";
import {
  FeatureDisabledNotice,
  QuantLabEmptyState,
  QuantLabTabLayout,
  TabRefreshRow,
} from "./QuantLabTabShell";
import { ApplyChangesNotice } from "@/components/product/ApplyChangesNotice";
import { ResearchReliabilityCard } from "./ResearchReliabilityCard";

export function ModelAdminTab() {
  const { t } = useTranslation();
  const [version, setVersion] = useState<Awaited<ReturnType<typeof getV2Version>> | null>(null);
  const [weights, setWeights] = useState<Awaited<ReturnType<typeof getV2SleeveWeights>> | null>(null);
  const [audit, setAudit] = useState<Awaited<ReturnType<typeof getV2Audit>> | null>(null);
  const [factorsAdmin, setFactorsAdmin] = useState<V2FactorsAdminResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [panelErrors, setPanelErrors] = useState<Record<string, string>>({});
  const [disabled, setDisabled] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setPanelErrors({});
    setDisabled(false);

    const [v, w, a, fa] = await Promise.allSettled([
      getV2Version(),
      getV2SleeveWeights("penny"),
      getV2Audit({ limit: 10 }),
      getV2FactorsAdmin("penny"),
    ]);

    const errors: Record<string, string> = {};

    if (v.status === "fulfilled") setVersion(v.value);
    else {
      setVersion(null);
      const msg = parseApiError(v.reason);
      if (isFeatureDisabledError(msg)) setDisabled(true);
      else errors.version = msg;
    }

    if (w.status === "fulfilled") setWeights(w.value);
    else {
      setWeights(null);
      const msg = parseApiError(w.reason);
      if (!isFeatureDisabledError(msg)) errors.weights = msg;
    }

    if (a.status === "fulfilled") setAudit(a.value);
    else {
      setAudit(null);
      const msg = parseApiError(a.reason);
      if (!isFeatureDisabledError(msg)) errors.audit = msg;
    }

    if (fa.status === "fulfilled") setFactorsAdmin(fa.value);
    else {
      setFactorsAdmin(null);
      const msg = parseApiError(fa.reason);
      if (!isFeatureDisabledError(msg)) errors.factors = msg;
    }

    setPanelErrors(errors);
    setLoading(false);
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const events = audit?.events ?? [];
  const factorCount = factorsAdmin?.factors?.length ?? 0;
  const hasContent = Boolean(version || weights || audit || factorsAdmin);
  const reliability = useMemo(
    () =>
      computeModelAdminReliability({
        version,
        weights,
        audit,
        factorsAdmin,
        disabled,
        panelErrors,
        loading,
      }),
    [version, weights, audit, factorsAdmin, disabled, panelErrors, loading]
  );

  return (
    <QuantLabTabLayout
      title={t.quantLab.tabModelAdmin}
      description={t.quantLab.hintModelAdmin}
      reliability={<ResearchReliabilityCard score={reliability} />}
      controls={<TabRefreshRow onRefresh={() => void load()} />}
      loading={loading}
      disabled={disabled}
      disabledMessage={t.quantLab.featureDisabled}
    >
      {disabled && <FeatureDisabledNotice message={t.quantLab.featureDisabled} />}
      {!hasContent && !disabled && Object.keys(panelErrors).length === 0 && (
        <QuantLabEmptyState message={t.quantLab.modelAdminEmpty} />
      )}
      {version && (
        <div className="surface-card p-4">
          <h3 className="text-sm font-semibold">{t.quantLab.activeVersion}</h3>
          <p className="mt-1 text-xs text-zinc-400">
            strategy: {version.strategy_version ?? "—"} · factor: {version.factor_model_version ?? "—"}
          </p>
        </div>
      )}
      {panelErrors.version && (
        <p className="text-xs text-amber-300">{panelErrors.version}</p>
      )}
      {factorsAdmin && (
        <div className="surface-card p-4">
          <h3 className="text-sm font-semibold">{t.quantLab.factorCatalog}</h3>
          <p className="text-xs text-zinc-500">
            {factorCount} factors · trade predictions: {factorsAdmin.trade_predictions_count} · outcomes:{" "}
            {factorsAdmin.trade_outcomes_count}
          </p>
        </div>
      )}
      {panelErrors.factors && <p className="text-xs text-amber-300">{panelErrors.factors}</p>}
      {weights && (
        <div className="surface-card p-4 space-y-2">
          <h3 className="text-sm font-semibold">{t.quantLab.dynamicWeights}</h3>
          <p className="text-xs text-zinc-500">
            {weights.sleeve} / {weights.regime} · dynamic={String(weights.dynamic_enabled)}
          </p>
          <ApplyChangesNotice />
        </div>
      )}
      {panelErrors.weights && <p className="text-xs text-amber-300">{panelErrors.weights}</p>}
      {audit && events.length > 0 && (
        <div className="surface-card p-4">
          <h3 className="text-sm font-semibold">{t.quantLab.auditLog}</h3>
          <ul className="mt-2 space-y-1 text-xs text-zinc-400">
            {events.slice(0, 8).map((e, i) => (
              <li key={e.id ?? i}>
                {e.event_type ?? "event"} {e.symbol ? `· ${e.symbol}` : ""}
              </li>
            ))}
          </ul>
        </div>
      )}
      {audit && events.length === 0 && (
        <p className="text-xs text-zinc-500">{t.quantLab.noAuditEvents}</p>
      )}
      {panelErrors.audit && <p className="text-xs text-amber-300">{panelErrors.audit}</p>}
    </QuantLabTabLayout>
  );
}
