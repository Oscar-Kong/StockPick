"use client";

import {
  fetchReviewQueue,
  getFormulaCandidateDetail,
  getHypothesisCandidateDetail,
  getRevisionCandidateDetail,
  getValidationResultByArtifact,
} from "@/lib/api/factorDiscovery/client";
import { parseFactorDiscoveryError } from "@/lib/api/factorDiscovery/errors";
import type {
  FormulaCandidateDetail,
  HypothesisCandidateDetail,
  ReviewQueueItem,
  RevisionCandidateDetail,
  ValidationResultDetail,
} from "@/lib/api/factorDiscovery/types";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { LoadingSkeleton } from "@/components/ui/LoadingSkeleton";
import { FormulaReviewCard } from "./FormulaReviewCard";
import { HypothesisReviewCard } from "./HypothesisReviewCard";
import { LlmInteractionDrawer } from "./LlmInteractionDrawer";
import { PromisingReviewPanel } from "./PromisingReviewPanel";
import { RevisionReviewCard } from "./RevisionReviewCard";
import { ValidationResultPanel } from "./ValidationResultPanel";
import { useCallback, useEffect, useState } from "react";

export function ReviewQueuePanel() {
  const [items, setItems] = useState<ReviewQueueItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<ReviewQueueItem | null>(null);
  const [interactionId, setInteractionId] = useState<string | null>(null);

  const load = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchReviewQueue({ limit: 50, offset: 0 }, signal);
      setItems(res.items);
      setTotal(res.total);
    } catch (e) {
      if (signal?.aborted) return;
      setError(parseFactorDiscoveryError(e).message);
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    load(controller.signal);
    return () => controller.abort();
  }, [load]);

  const refresh = () => {
    load();
    setSelected((s) => (s ? { ...s } : null));
  };

  if (loading && items.length === 0) return <LoadingSkeleton lines={5} />;
  if (error && items.length === 0) return <ErrorState message={error} onRetry={() => load()} />;
  if (items.length === 0) {
    return (
      <EmptyState
        title="Review queue empty"
        message="No hypotheses, formulas, revisions, or promising candidates awaiting attention."
      />
    );
  }

  return (
    <div className="grid gap-4 lg:grid-cols-[320px_1fr]">
      <ul className="space-y-2" aria-label="Review queue">
        <p className="text-xs text-zinc-500">{total} item(s)</p>
        {items.map((item) => (
          <li key={`${item.review_type}-${item.candidate_id}`}>
            <button
              type="button"
              className={`w-full rounded-lg border p-3 text-left text-xs ${selected?.candidate_id === item.candidate_id ? "border-zinc-400 bg-zinc-100 dark:border-zinc-500 dark:bg-zinc-800" : "border-zinc-200 dark:border-zinc-700"}`}
              onClick={() => setSelected(item)}
            >
              <p className="font-medium capitalize">{item.review_type.replace("_", " ")}</p>
              <p className="truncate">{item.candidate_name}</p>
              <p className="text-zinc-500">{item.review_reason}</p>
              {item.warning_count > 0 ? <p className="text-amber-600">{item.warning_count} warning(s)</p> : null}
            </button>
          </li>
        ))}
      </ul>

      <div>
        {selected ? (
          <ReviewDetailPane
            item={selected}
            onRefresh={refresh}
            onViewInteraction={setInteractionId}
          />
        ) : (
          <p className="text-sm text-zinc-500">Select a queue item to review.</p>
        )}
      </div>

      <LlmInteractionDrawer
        interactionId={interactionId}
        open={Boolean(interactionId)}
        onClose={() => setInteractionId(null)}
      />
    </div>
  );
}

function ReviewDetailPane({
  item,
  onRefresh,
  onViewInteraction,
}: {
  item: ReviewQueueItem;
  onRefresh: () => void;
  onViewInteraction: (id: string) => void;
}) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [hypothesis, setHypothesis] = useState<HypothesisCandidateDetail | null>(null);
  const [formula, setFormula] = useState<FormulaCandidateDetail | null>(null);
  const [revision, setRevision] = useState<RevisionCandidateDetail | null>(null);
  const [validation, setValidation] = useState<ValidationResultDetail | null>(null);
  const [promisingPolicy, setPromisingPolicy] = useState<Record<string, unknown> | null>(null);

  const load = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    setError(null);
    try {
      if (item.review_type === "hypothesis") {
        setHypothesis((await getHypothesisCandidateDetail(item.candidate_id, signal)) as HypothesisCandidateDetail);
      } else if (item.review_type === "formula") {
        setFormula((await getFormulaCandidateDetail(item.candidate_id, signal)) as FormulaCandidateDetail);
      } else if (item.review_type === "revision") {
        setRevision((await getRevisionCandidateDetail(item.candidate_id, signal)) as RevisionCandidateDetail);
      } else if (item.review_type === "promising" && item.artifact_id) {
        const res = (await getValidationResultByArtifact(item.artifact_id, signal)) as ValidationResultDetail;
        setValidation(res);
        setPromisingPolicy(res.promising_policy);
      }
    } catch (e) {
      if (signal?.aborted) return;
      setError(parseFactorDiscoveryError(e).message);
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, [item]);

  useEffect(() => {
    const controller = new AbortController();
    load(controller.signal);
    return () => controller.abort();
  }, [load]);

  if (loading) return <LoadingSkeleton lines={8} />;
  if (error) return <ErrorState message={error} onRetry={() => load()} />;

  if (hypothesis) {
    return (
      <HypothesisReviewCard detail={hypothesis} onRefresh={() => { load(); onRefresh(); }} onViewInteraction={onViewInteraction} />
    );
  }
  if (formula) {
    return <FormulaReviewCard detail={formula} onRefresh={() => { load(); onRefresh(); }} onViewInteraction={onViewInteraction} />;
  }
  if (revision) {
    return <RevisionReviewCard detail={revision} onRefresh={() => { load(); onRefresh(); }} />;
  }
  if (item.review_type === "promising") {
    return (
      <div className="space-y-4">
        <PromisingReviewPanel policy={promisingPolicy} artifactId={item.artifact_id} sessionId={item.session_id} />
        {validation ? <ValidationResultPanel result={validation} /> : null}
      </div>
    );
  }

  return <p className="text-sm text-zinc-500">Unable to load candidate detail.</p>;
}
