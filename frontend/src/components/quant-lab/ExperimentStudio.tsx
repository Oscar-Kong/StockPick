"use client";

import {
  createResearchExperiment,
  getExperimentJob,
  getExperimentPresets,
  getExperimentTemplates,
  launchResearchExperiment,
  updateResearchExperiment,
  validateResearchExperiment,
} from "@/lib/api";
import { parseApiError } from "@/lib/apiError";
import {
  buildExperimentStudioHref,
  defaultWalkForwardDates,
  type ExperimentPresetId,
  type ExperimentStudioStep,
  type ExperimentType,
  type UniverseSource,
} from "@/lib/experimentStudio";
import type {
  ExperimentJobResponse,
  ExperimentPresetInfo,
  ExperimentTemplateInfo,
  ExperimentValidationResponse,
} from "@/lib/types";
import type { Bucket } from "@/lib/types";
import { useTranslation, useTRef } from "@/lib/i18n";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { BucketSelect } from "./QuantLabTabShell";
import { ErrorState } from "@/components/ui/ErrorState";
import { LoadingSkeleton } from "@/components/ui/LoadingSkeleton";
import { ResearchOnlyBadge } from "@/components/ui/ResearchOnlyBadge";

interface ExperimentStudioProps {
  sleeve: Bucket;
  onSleeveChange: (sleeve: Bucket) => void;
}

const STEP_ORDER: ExperimentStudioStep[] = ["choose", "configure", "review", "run", "status", "result"];

export function ExperimentStudio({ sleeve, onSleeveChange }: ExperimentStudioProps) {
  const { t } = useTranslation();
  const tRef = useTRef();
  const router = useRouter();
  const searchParams = useSearchParams();
  const step = (searchParams.get("step") as ExperimentStudioStep) || "choose";
  const template = (searchParams.get("template") as ExperimentType | null) || null;
  const experimentId = searchParams.get("experiment");
  const jobId = searchParams.get("job");
  const ideaId = searchParams.get("idea");

  const [templates, setTemplates] = useState<ExperimentTemplateInfo[]>([]);
  const [presets, setPresets] = useState<ExperimentPresetInfo[]>([]);
  const [loadingMeta, setLoadingMeta] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [validation, setValidation] = useState<ExperimentValidationResponse | null>(null);
  const [job, setJob] = useState<ExperimentJobResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const runLockRef = useRef(false);

  const [name, setName] = useState("");
  const [preset, setPreset] = useState<ExperimentPresetId>("standard_research");
  const [universeSource, setUniverseSource] = useState<UniverseSource>("full_bucket");
  const [customSymbols, setCustomSymbols] = useState("AAPL, MSFT, NVDA");
  const [notes, setNotes] = useState("");
  const [params, setParams] = useState<Record<string, unknown>>(() => {
    const dates = defaultWalkForwardDates();
    return { ...dates, forward_horizons: [20, 60], factors: ["momentum"] };
  });

  const navigate = useCallback(
    (opts: Parameters<typeof buildExperimentStudioHref>[0]) => {
      router.push(buildExperimentStudioHref({ ...opts, experimentId: opts.experimentId ?? experimentId, ideaId: opts.ideaId ?? ideaId }));
    },
    [router, experimentId, ideaId]
  );

  useEffect(() => {
    void (async () => {
      setLoadingMeta(true);
      try {
        const [tmpl, prs] = await Promise.all([getExperimentTemplates(), getExperimentPresets()]);
        setTemplates(tmpl.templates);
        setPresets(prs.presets);
      } catch (e) {
        setError(parseApiError(e, tRef.current.quantLab.loadFailed));
      } finally {
        setLoadingMeta(false);
      }
    })();
  }, [tRef]);

  useEffect(() => {
    if (step !== "review" && step !== "run") return;
    if (!template) return;
    void (async () => {
      try {
        const res = await validateResearchExperiment({
          experiment_type: template,
          sleeve,
          preset,
          universe_definition: {
            source: universeSource,
            symbols: customSymbols.split(/[,\s]+/).filter(Boolean),
          },
          parameters: params,
        });
        setValidation(res);
      } catch (e) {
        setError(parseApiError(e, tRef.current.quantLab.loadFailed));
      }
    })();
  }, [step, template, sleeve, preset, universeSource, customSymbols, params, tRef]);

  useEffect(() => {
    if (!jobId || (step !== "status" && step !== "run" && step !== "result")) return;
    let cancelled = false;
    const poll = async () => {
      try {
        const j = await getExperimentJob(jobId);
        if (cancelled) return;
        setJob(j);
        if (j.status === "completed" && step === "status") {
          navigate({ step: "result", jobId, template: template ?? undefined });
        }
      } catch {
        /* retry next tick */
      }
    };
    void poll();
    const id = window.setInterval(() => void poll(), 2000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [jobId, step, navigate, template]);

  const selectedTemplate = useMemo(
    () => templates.find((x) => x.experiment_type === template) ?? null,
    [templates, template]
  );

  const onChooseTemplate = (expType: ExperimentType) => {
    setName(selectedTemplate?.title ?? expType.replace(/_/g, " "));
    navigate({ step: "configure", template: expType });
  };

  const onSaveDraft = async () => {
    if (!template || !name.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const body = {
        idea_id: ideaId ?? undefined,
        name: name.trim(),
        experiment_type: template,
        sleeve,
        preset,
        notes,
        universe_definition: {
          source: universeSource,
          symbols: customSymbols.split(/[,\s]+/).filter(Boolean),
        },
        parameters: params,
        hypothesis: validation?.checks.find((c) => c.key === "hypothesis")?.value?.toString() ?? "",
        null_hypothesis: validation?.checks.find((c) => c.key === "null_hypothesis")?.value?.toString() ?? "",
        success_criteria: validation?.checks.find((c) => c.key === "success_criteria")?.value?.toString() ?? "",
        failure_criteria: validation?.checks.find((c) => c.key === "failure_criteria")?.value?.toString() ?? "",
      };
      const exp = experimentId
        ? await updateResearchExperiment(experimentId, body)
        : await createResearchExperiment(body);
      const id = String(exp.id ?? "");
      navigate({ step: "configure", template, experimentId: id });
    } catch (e) {
      setError(parseApiError(e, tRef.current.quantLab.runFailed));
    } finally {
      setBusy(false);
    }
  };

  const onRun = async () => {
    if (!template || runLockRef.current || busy) return;
    if (validation && !validation.can_run) return;
    runLockRef.current = true;
    setBusy(true);
    setError(null);
    try {
      let expId = experimentId;
      if (!expId) {
        const exp = await createResearchExperiment({
          idea_id: ideaId ?? undefined,
          name: name.trim() || template,
          experiment_type: template,
          sleeve,
          preset,
          notes,
          universe_definition: { source: universeSource, symbols: customSymbols.split(/[,\s]+/).filter(Boolean) },
          parameters: params,
        });
        expId = String(exp.id ?? "");
      }
      const launch = await launchResearchExperiment(expId);
      if (launch.duplicate_blocked) {
        setError(t.quantLab.studioDuplicateRun);
        navigate({ step: "status", experimentId: expId, jobId: launch.job_id, template });
        return;
      }
      navigate({ step: "status", experimentId: expId, jobId: launch.job_id, template });
    } catch (e) {
      setError(parseApiError(e, tRef.current.quantLab.runFailed));
    } finally {
      setBusy(false);
      runLockRef.current = false;
    }
  };

  if (loadingMeta && step === "choose") return <LoadingSkeleton lines={5} />;

  const stepIndex = STEP_ORDER.indexOf(step);

  return (
    <div className="space-y-4 text-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <BucketSelect label={t.common.bucket} value={sleeve} onChange={(v) => onSleeveChange(v as Bucket)} />
        <ResearchOnlyBadge tooltip={t.quantLab.researchOnlyWarning} />
      </div>

      <nav className="flex flex-wrap gap-1 text-xs" aria-label={t.quantLab.studioStepsAria}>
        {STEP_ORDER.slice(0, 4).map((s, i) => (
          <span
            key={s}
            className={`rounded px-2 py-0.5 tabular-nums ${i <= stepIndex ? "bg-zinc-800 text-zinc-200" : "text-zinc-600"}`}
          >
            {i + 1}. {t.quantLab[`studioStep_${s}` as keyof typeof t.quantLab] as string}
          </span>
        ))}
      </nav>

      {error && <ErrorState message={error} onRetry={() => setError(null)} />}

      {step === "choose" && (
        <section className="space-y-2">
          <p className="text-zinc-400">{t.quantLab.studioChooseHint}</p>
          <ul className="grid gap-2 sm:grid-cols-2">
            {templates.map((tmpl) => (
              <li key={tmpl.experiment_type}>
                <button
                  type="button"
                  className="w-full rounded-lg border border-zinc-800 bg-zinc-950/50 px-3 py-2 text-left hover:border-zinc-600"
                  onClick={() => onChooseTemplate(tmpl.experiment_type as ExperimentType)}
                >
                  <p className="font-medium text-zinc-100">{tmpl.title}</p>
                  <p className="mt-1 text-xs text-zinc-500">{tmpl.description}</p>
                </button>
              </li>
            ))}
          </ul>
          <p className="text-xs text-zinc-600">{t.quantLab.studioLegacyLink}</p>
        </section>
      )}

      {step === "configure" && template && (
        <section className="surface-card space-y-3 p-4">
          <h3 className="font-semibold text-zinc-100">{selectedTemplate?.title ?? template}</h3>
          <label className="block text-xs text-zinc-500">
            {t.quantLab.studioName}
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="mt-1 w-full rounded border border-zinc-700 bg-zinc-950 px-2 py-1"
            />
          </label>
          <label className="block text-xs text-zinc-500">
            {t.quantLab.studioPreset}
            <select
              value={preset}
              onChange={(e) => setPreset(e.target.value as ExperimentPresetId)}
              className="mt-1 w-full rounded border border-zinc-700 bg-zinc-950 px-2 py-1"
            >
              {presets.map((p) => (
                <option key={p.preset_id} value={p.preset_id}>
                  {p.title}
                </option>
              ))}
              <option value="custom">{t.quantLab.studioPresetCustom}</option>
            </select>
          </label>
          {preset !== "custom" && (
            <details className="text-xs text-zinc-500">
              <summary className="cursor-pointer text-zinc-400">{t.quantLab.studioPresetParams}</summary>
              <ul className="mt-2 space-y-1">
                {presets
                  .find((p) => p.preset_id === preset)
                  ?.parameters.map((p) => (
                    <li key={p.key} className="tabular-nums">
                      {p.key}: {String(p.value)}
                    </li>
                  ))}
              </ul>
            </details>
          )}
          <label className="block text-xs text-zinc-500">
            {t.quantLab.studioUniverse}
            <select
              value={universeSource}
              onChange={(e) => setUniverseSource(e.target.value as UniverseSource)}
              className="mt-1 w-full rounded border border-zinc-700 bg-zinc-950 px-2 py-1"
            >
              {UNIVERSE_SOURCE_OPTIONS.map((s) => (
                <option key={s} value={s}>
                  {t.quantLab[`studioUniverse_${s}` as keyof typeof t.quantLab] as string}
                </option>
              ))}
            </select>
          </label>
          {universeSource === "custom_symbols" && (
            <textarea
              value={customSymbols}
              onChange={(e) => setCustomSymbols(e.target.value)}
              rows={2}
              className="w-full rounded border border-zinc-700 bg-zinc-950 px-2 py-1 text-sm"
              placeholder={t.quantLab.studioCustomSymbols}
            />
          )}
          {template === "walk_forward" && (
            <div className="flex flex-wrap gap-3">
              <label className="text-xs text-zinc-500">
                {t.quantLab.startDate}
                <input
                  type="date"
                  value={String(params.start_date ?? "")}
                  onChange={(e) => setParams((p) => ({ ...p, start_date: e.target.value }))}
                  className="ml-2 rounded border border-zinc-700 bg-zinc-950 px-2 py-1"
                />
              </label>
              <label className="text-xs text-zinc-500">
                {t.quantLab.endDate}
                <input
                  type="date"
                  value={String(params.end_date ?? "")}
                  onChange={(e) => setParams((p) => ({ ...p, end_date: e.target.value }))}
                  className="ml-2 rounded border border-zinc-700 bg-zinc-950 px-2 py-1"
                />
              </label>
            </div>
          )}
          {template === "factor_validation" && (
            <label className="block text-xs text-zinc-500">
              {t.quantLab.studioFactors}
              <input
                value={String((params.factors as string[])?.join(", ") ?? params.factors ?? "")}
                onChange={(e) =>
                  setParams((p) => ({
                    ...p,
                    factors: e.target.value.split(/[,\s]+/).filter(Boolean),
                  }))
                }
                className="mt-1 w-full rounded border border-zinc-700 bg-zinc-950 px-2 py-1"
              />
            </label>
          )}
          {template === "similar_signal" && (
            <label className="block text-xs text-zinc-500">
              {t.quantLab.studioSymbol}
              <input
                value={String(params.symbol ?? "")}
                onChange={(e) => setParams((p) => ({ ...p, symbol: e.target.value.toUpperCase() }))}
                className="mt-1 w-full rounded border border-zinc-700 bg-zinc-950 px-2 py-1"
              />
            </label>
          )}
          {template === "portfolio_policy" && (
            <label className="block text-xs text-zinc-500">
              {t.quantLab.studioPolicy}
              <select
                value={String(params.policy ?? "equal_weight")}
                onChange={(e) => setParams((p) => ({ ...p, policy: e.target.value }))}
                className="mt-1 w-full rounded border border-zinc-700 bg-zinc-950 px-2 py-1"
              >
                <option value="equal_weight">equal_weight</option>
                <option value="inverse_vol">inverse_vol</option>
                <option value="top_n_momentum">top_n_momentum</option>
              </select>
            </label>
          )}
          {template === "pairs_discovery" && (
            <p className="text-xs text-amber-300/90">{t.quantLab.cointegrationTooltip}</p>
          )}
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={2}
            placeholder={t.quantLab.studioNotes}
            className="w-full rounded border border-zinc-700 bg-zinc-950 px-2 py-1"
          />
          <div className="flex flex-wrap gap-2">
            <button type="button" className="rounded border border-zinc-700 px-3 py-1 text-xs" onClick={() => navigate({ step: "choose" })}>
              {t.quantLab.studioBack}
            </button>
            <button type="button" className="rounded border border-zinc-700 px-3 py-1 text-xs" disabled={busy} onClick={() => void onSaveDraft()}>
              {t.quantLab.studioSaveDraft}
            </button>
            <button type="button" className="rounded bg-zinc-100 px-3 py-1 text-xs font-medium text-zinc-900" onClick={() => navigate({ step: "review", template })}>
              {t.quantLab.studioContinueReview}
            </button>
          </div>
        </section>
      )}

      {step === "review" && template && (
        <section className="surface-card space-y-3 p-4">
          <h3 className="font-semibold text-zinc-100">{t.quantLab.studioReviewTitle}</h3>
          {!validation ? (
            <LoadingSkeleton lines={4} />
          ) : (
            <>
              <ul className="space-y-1 text-xs">
                {validation.checks.map((c) => (
                  <li key={c.key} className="flex justify-between gap-2">
                    <span className="text-zinc-400">{c.label}</span>
                    <span
                      className={
                        c.status === "error"
                          ? "text-red-400"
                          : c.status === "warning"
                            ? "text-amber-300"
                            : "text-emerald-400"
                      }
                    >
                      {c.detail || String(c.value ?? c.status)}
                    </span>
                  </li>
                ))}
              </ul>
              {validation.major_limitations.length > 0 && (
                <ul className="text-xs text-amber-300">
                  {validation.major_limitations.map((m) => (
                    <li key={m}>{m}</li>
                  ))}
                </ul>
              )}
              <p className="text-xs text-zinc-500 tabular-nums">
                {t.quantLab.studioSymbolCount}: {validation.symbol_count} · {t.quantLab.studioDataCutoff}:{" "}
                {validation.data_cutoff}
              </p>
            </>
          )}
          <div className="flex flex-wrap gap-2">
            <button type="button" className="rounded border border-zinc-700 px-3 py-1 text-xs" onClick={() => navigate({ step: "configure", template })}>
              {t.quantLab.studioBack}
            </button>
            <button
              type="button"
              className="rounded bg-blue-600/90 px-3 py-1 text-xs text-white disabled:opacity-40"
              disabled={!validation?.can_run || busy}
              onClick={() => void onRun()}
            >
              {busy ? t.common.running : t.quantLab.studioRun}
            </button>
          </div>
        </section>
      )}

      {(step === "status" || step === "result") && (
        <section className="surface-card space-y-3 p-4">
          <h3 className="font-semibold text-zinc-100">
            {step === "result" ? t.quantLab.studioResultTitle : t.quantLab.studioStatusTitle}
          </h3>
          {!job ? (
            <LoadingSkeleton lines={4} />
          ) : (
            <>
              <p className="text-xs text-zinc-400">
                {t.quantLab.runStatus}: <span className="text-zinc-200">{job.status}</span>
                {job.run_id && (
                  <>
                    {" "}
                    · run <span className="tabular-nums text-zinc-300">{job.run_id}</span>
                  </>
                )}
              </p>
              {job.last_success_run_id && job.status === "failed" && (
                <p className="text-xs text-amber-300">{t.quantLab.studioLastSuccess}: {job.last_success_run_id}</p>
              )}
              <ul className="space-y-1 text-xs">
                {job.stages.map((s) => (
                  <li key={s.stage} className="flex justify-between gap-2">
                    <span className="text-zinc-500">{s.stage.replace(/_/g, " ")}</span>
                    <span
                      className={
                        s.status === "completed"
                          ? "text-emerald-400"
                          : s.status === "failed"
                            ? "text-red-400"
                            : s.status === "running"
                              ? "text-blue-300"
                              : "text-zinc-600"
                      }
                    >
                      {s.status}
                    </span>
                  </li>
                ))}
              </ul>
              {job.error_message && <p className="text-xs text-red-400">{job.error_message}</p>}
            </>
          )}
          {step === "result" && job?.run_id && (
            <button
              type="button"
              className="rounded border border-zinc-700 px-3 py-1 text-xs"
              onClick={() => router.push(`/quant-lab?section=results`)}
            >
              {t.quantLab.studioOpenResults}
            </button>
          )}
        </section>
      )}
    </div>
  );
}

const UNIVERSE_SOURCE_OPTIONS: UniverseSource[] = [
  "latest_scan",
  "saved_scan",
  "watchlist",
  "portfolio_holdings",
  "full_bucket",
  "custom_symbols",
];
