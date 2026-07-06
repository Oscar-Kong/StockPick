"use client";

import {
  createResearchExperiment,
  createResearchIdea,
  duplicateResearchIdea,
  generateResearchIdeas,
  listResearchIdeas,
  updateResearchIdea,
} from "@/lib/api";
import { parseApiError } from "@/lib/apiError";
import type { Bucket, ResearchIdea, ResearchIdeaStatus } from "@/lib/types";
import { buildExperimentStudioHref } from "@/lib/experimentStudio";
import { useTranslation, useTRef } from "@/lib/i18n";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { ErrorState } from "@/components/ui/ErrorState";
import { LoadingSkeleton } from "@/components/ui/LoadingSkeleton";

const OPEN_STATUSES: ResearchIdeaStatus[] = ["new", "saved", "ready_to_test", "running"];

interface IdeasBoardTabProps {
  sleeve: Bucket;
  onSleeveChange?: (sleeve: Bucket) => void;
}

export function IdeasBoardTab({ sleeve }: IdeasBoardTabProps) {
  const { t } = useTranslation();
  const tRef = useTRef();
  const router = useRouter();
  const [ideas, setIdeas] = useState<ResearchIdea[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("open");
  const [sourceFilter, setSourceFilter] = useState<string>("all");
  const [busyId, setBusyId] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [draftTitle, setDraftTitle] = useState("");
  const [draftHypothesis, setDraftHypothesis] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [editHypothesis, setEditHypothesis] = useState("");
  const [editNotes, setEditNotes] = useState("");
  const [editPriority, setEditPriority] = useState(50);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await listResearchIdeas({ sleeve, limit: 100 });
      setIdeas(res.ideas);
    } catch (e) {
      setIdeas([]);
      setError(parseApiError(e, tRef.current.quantLab.loadFailed));
    } finally {
      setLoading(false);
    }
  }, [sleeve, tRef]);

  useEffect(() => {
    void load();
  }, [load]);

  const filtered = useMemo(() => {
    let list = [...ideas];
    if (statusFilter === "open") {
      list = list.filter((i) => OPEN_STATUSES.includes(i.status));
    } else if (statusFilter !== "all") {
      list = list.filter((i) => i.status === statusFilter);
    }
    if (sourceFilter === "user_created") {
      list = list.filter((i) => i.source_type === "user_created");
    } else if (sourceFilter === "generated") {
      list = list.filter((i) => i.source_type !== "user_created");
    } else if (sourceFilter !== "all") {
      list = list.filter((i) => i.source_type === sourceFilter);
    }
    if (search.trim()) {
      const q = search.toLowerCase();
      list = list.filter(
        (i) =>
          i.title.toLowerCase().includes(q) ||
          i.hypothesis.toLowerCase().includes(q) ||
          i.why_now.toLowerCase().includes(q)
      );
    }
    return list.sort((a, b) => b.priority - a.priority || b.confidence - a.confidence);
  }, [ideas, search, statusFilter, sourceFilter]);

  const mutate = async (id: string, fn: () => Promise<unknown>) => {
    setBusyId(id);
    try {
      await fn();
      await load();
    } catch (e) {
      setError(parseApiError(e, tRef.current.quantLab.runFailed));
    } finally {
      setBusyId(null);
    }
  };

  const onCreateManual = async () => {
    if (!draftTitle.trim()) return;
    setBusyId("create");
    try {
      await createResearchIdea({
        title: draftTitle.trim(),
        hypothesis: draftHypothesis,
        source_type: "user_created",
        sleeve,
        status: "saved",
      });
      setDraftTitle("");
      setDraftHypothesis("");
      setShowCreate(false);
      await load();
    } catch (e) {
      setError(parseApiError(e, tRef.current.quantLab.runFailed));
    } finally {
      setBusyId(null);
    }
  };

  const onGenerate = async () => {
    setBusyId("generate");
    try {
      await generateResearchIdeas({ sleeve, limit: 8 });
      await load();
    } catch (e) {
      setError(parseApiError(e, tRef.current.quantLab.runFailed));
    } finally {
      setBusyId(null);
    }
  };

  const startEdit = (idea: ResearchIdea) => {
    setEditingId(idea.id);
    setEditTitle(idea.title);
    setEditHypothesis(idea.hypothesis);
    setEditNotes(idea.user_notes);
    setEditPriority(idea.priority);
  };

  const onSaveEdit = async (id: string) => {
    await mutate(id, () =>
      updateResearchIdea(id, {
        title: editTitle.trim(),
        hypothesis: editHypothesis,
        user_notes: editNotes,
        priority: editPriority,
      })
    );
    setEditingId(null);
  };

  const onConfigureExperiment = async (idea: ResearchIdea) => {
    await mutate(idea.id, async () => {
      const exp = await createResearchExperiment({
        idea_id: idea.id,
        name: idea.title.slice(0, 120),
        experiment_type: idea.suggested_experiment_type || "factor_validation",
        sleeve: idea.sleeve || sleeve,
        parameters: idea.suggested_parameters,
        preset: "exploratory",
      });
      const expId = typeof exp.id === "string" ? exp.id : null;
      await updateResearchIdea(idea.id, { status: "ready_to_test" });
      router.push(
        buildExperimentStudioHref({
          step: "configure",
          template: (idea.suggested_experiment_type as import("@/lib/experimentStudio").ExperimentType) || "walk_forward",
          experimentId: expId ?? undefined,
          ideaId: idea.id,
        })
      );
    });
  };

  if (loading) return <LoadingSkeleton lines={5} />;

  return (
    <div className="space-y-3 text-sm">
      <div className="flex flex-wrap items-end gap-2">
        <label className="text-xs text-zinc-500">
          {t.quantLab.ideasSearch}
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="ml-2 rounded border border-zinc-700 bg-zinc-950 px-2 py-1 text-sm"
          />
        </label>
        <label className="text-xs text-zinc-500">
          {t.quantLab.ideasStatus}
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="ml-2 rounded border border-zinc-700 bg-zinc-950 px-2 py-1 text-sm"
          >
            <option value="open">{t.quantLab.ideasFilterOpen}</option>
            <option value="all">{t.quantLab.ideasFilterAll}</option>
            <option value="archived">{t.quantLab.ideasFilterArchived}</option>
          </select>
        </label>
        <label className="text-xs text-zinc-500">
          {t.quantLab.ideasSource}
          <select
            value={sourceFilter}
            onChange={(e) => setSourceFilter(e.target.value)}
            className="ml-2 rounded border border-zinc-700 bg-zinc-950 px-2 py-1 text-sm"
          >
            <option value="all">{t.quantLab.ideasFilterAll}</option>
            <option value="user_created">{t.quantLab.ideasSourceUser}</option>
            <option value="generated">{t.quantLab.ideasSourceGenerated}</option>
          </select>
        </label>
        <button
          type="button"
          className="rounded border border-zinc-700 px-2 py-1 text-xs"
          disabled={busyId === "generate"}
          onClick={() => void onGenerate()}
        >
          {t.quantLab.overviewGenerateIdeas}
        </button>
        <button type="button" className="rounded border border-zinc-700 px-2 py-1 text-xs" onClick={() => setShowCreate((v) => !v)}>
          {t.quantLab.ideasCreateManual}
        </button>
      </div>

      {showCreate && (
        <div className="surface-card space-y-2 p-3">
          <input
            value={draftTitle}
            onChange={(e) => setDraftTitle(e.target.value)}
            placeholder={t.quantLab.ideasTitlePlaceholder}
            className="w-full rounded border border-zinc-700 bg-zinc-950 px-2 py-1"
          />
          <textarea
            value={draftHypothesis}
            onChange={(e) => setDraftHypothesis(e.target.value)}
            placeholder={t.quantLab.ideasHypothesisPlaceholder}
            rows={2}
            className="w-full rounded border border-zinc-700 bg-zinc-950 px-2 py-1"
          />
          <button
            type="button"
            disabled={busyId === "create"}
            className="rounded bg-zinc-100 px-3 py-1 text-xs font-medium text-zinc-900"
            onClick={() => void onCreateManual()}
          >
            {t.quantLab.ideasSave}
          </button>
        </div>
      )}

      {error && <ErrorState message={error} onRetry={() => void load()} />}

      {filtered.length === 0 ? (
        <p className="text-sm text-zinc-500">{t.quantLab.overviewNoIdeas}</p>
      ) : (
        <ul className="space-y-2">
          {filtered.map((idea) => (
            <li key={idea.id} className="surface-card p-3">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="min-w-0 flex-1">
                  {editingId === idea.id ? (
                    <div className="space-y-2">
                      <input
                        value={editTitle}
                        onChange={(e) => setEditTitle(e.target.value)}
                        className="w-full rounded border border-zinc-700 bg-zinc-950 px-2 py-1"
                      />
                      <textarea
                        value={editHypothesis}
                        onChange={(e) => setEditHypothesis(e.target.value)}
                        rows={2}
                        className="w-full rounded border border-zinc-700 bg-zinc-950 px-2 py-1"
                      />
                      <label className="block text-xs text-zinc-500">
                        {t.quantLab.ideasNotes}
                        <textarea
                          aria-label={t.quantLab.ideasNotes}
                          value={editNotes}
                          onChange={(e) => setEditNotes(e.target.value)}
                          rows={2}
                          className="mt-1 w-full rounded border border-zinc-700 bg-zinc-950 px-2 py-1"
                        />
                      </label>
                      <label className="block text-xs text-zinc-500">
                        {t.quantLab.ideasPriority}
                        <input
                          type="number"
                          min={0}
                          max={100}
                          value={editPriority}
                          onChange={(e) => setEditPriority(Number(e.target.value))}
                          className="ml-2 w-16 rounded border border-zinc-700 bg-zinc-950 px-2 py-1 tabular-nums"
                        />
                      </label>
                      <div className="flex gap-2">
                        <button
                          type="button"
                          className="rounded bg-zinc-100 px-2 py-1 text-xs font-medium text-zinc-900"
                          disabled={busyId === idea.id}
                          onClick={() => void onSaveEdit(idea.id)}
                        >
                          {t.quantLab.ideasSaveEdits}
                        </button>
                        <button
                          type="button"
                          className="rounded border border-zinc-700 px-2 py-1 text-xs"
                          onClick={() => setEditingId(null)}
                        >
                          {t.quantLab.ideasCancelEdit}
                        </button>
                      </div>
                    </div>
                  ) : (
                    <>
                      <p className="font-medium text-zinc-100">{idea.title}</p>
                      <p className="mt-1 text-xs leading-relaxed text-zinc-400">{idea.hypothesis}</p>
                      {idea.why_now && <p className="mt-1 text-xs text-blue-300/90">{idea.why_now}</p>}
                      {idea.user_notes && (
                        <p className="mt-1 text-xs text-zinc-500">
                          {t.quantLab.ideasNotes}: {idea.user_notes}
                        </p>
                      )}
                      <p className="mt-1 text-xs text-zinc-500">
                        {idea.source_type} · {idea.suggested_experiment_type ?? "—"} · priority {idea.priority}
                      </p>
                    </>
                  )}
                </div>
                {editingId !== idea.id && (
                  <span className="rounded bg-zinc-900 px-2 py-0.5 text-xs text-zinc-400">{idea.status}</span>
                )}
              </div>
              {editingId !== idea.id && (
              <div className="mt-2 flex flex-wrap gap-2">
                <button
                  type="button"
                  className="rounded bg-blue-600/90 px-2 py-1 text-xs text-white"
                  disabled={busyId === idea.id}
                  onClick={() => void onConfigureExperiment(idea)}
                >
                  {t.quantLab.ideasConfigureExperiment}
                </button>
                <button
                  type="button"
                  className="rounded border border-zinc-700 px-2 py-1 text-xs"
                  disabled={busyId === idea.id}
                  onClick={() => startEdit(idea)}
                >
                  {t.quantLab.ideasEdit}
                </button>
                <button
                  type="button"
                  className="rounded border border-zinc-700 px-2 py-1 text-xs"
                  disabled={busyId === idea.id}
                  onClick={() => void mutate(idea.id, () => updateResearchIdea(idea.id, { status: "ready_to_test" }))}
                >
                  {t.quantLab.ideasMarkReady}
                </button>
                <button
                  type="button"
                  className="rounded border border-zinc-700 px-2 py-1 text-xs"
                  disabled={busyId === idea.id}
                  onClick={() => void mutate(idea.id, () => duplicateResearchIdea(idea.id))}
                >
                  {t.quantLab.ideasDuplicate}
                </button>
                <button
                  type="button"
                  className="rounded border border-zinc-700 px-2 py-1 text-xs"
                  disabled={busyId === idea.id}
                  onClick={() => void mutate(idea.id, () => updateResearchIdea(idea.id, { status: "archived" }))}
                >
                  {t.quantLab.ideasArchive}
                </button>
              </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
