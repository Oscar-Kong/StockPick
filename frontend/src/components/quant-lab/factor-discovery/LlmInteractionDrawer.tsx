"use client";

import { getLlmInteraction } from "@/lib/api/factorDiscovery/client";
import { parseFactorDiscoveryError } from "@/lib/api/factorDiscovery/errors";
import { LoadingSkeleton } from "@/components/ui/LoadingSkeleton";
import { useEffect, useRef, useState } from "react";

export function LlmInteractionDrawer({
  interactionId,
  open,
  onClose,
}: {
  interactionId: string | null;
  open: boolean;
  onClose: () => void;
}) {
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open || !interactionId) return;
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    getLlmInteraction(interactionId, controller.signal)
      .then(setData)
      .catch((e) => {
        if (controller.signal.aborted) return;
        setError(parseFactorDiscoveryError(e).message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [open, interactionId]);

  useEffect(() => {
    if (open) closeRef.current?.focus();
  }, [open]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/40" role="presentation" onClick={onClose}>
      <aside
        className="h-full w-full max-w-lg overflow-y-auto bg-white p-4 shadow-xl dark:bg-zinc-900"
        role="dialog"
        aria-modal="true"
        aria-labelledby="llm-drawer-title"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-2">
          <div>
            <h2 id="llm-drawer-title" className="text-base font-semibold">
              LLM interaction
            </h2>
            <p className="text-xs text-zinc-500">AI-generated research content</p>
          </div>
          <button ref={closeRef} type="button" className="rounded border px-2 py-1 text-sm" onClick={onClose}>
            Close
          </button>
        </div>

        {loading ? <LoadingSkeleton lines={6} /> : null}
        {error ? (
          <p className="mt-4 text-sm text-red-600" role="alert">
            {error}
          </p>
        ) : null}

        {data ? (
          <dl className="mt-4 space-y-2 text-sm">
            {[
              "interaction_id",
              "operation_type",
              "provider_id",
              "model_id",
              "prompt_template_id",
              "prompt_template_version",
              "structured_output_mode",
              "input_token_count",
              "output_token_count",
              "total_token_count",
              "retry_count",
              "finish_reason",
              "status",
              "safe_error_code",
              "safe_error_summary",
              "created_at",
              "completed_at",
            ].map((key) =>
              data[key] != null ? (
                <div key={key}>
                  <dt className="text-zinc-500">{key.replace(/_/g, " ")}</dt>
                  <dd className="break-all">{String(data[key])}</dd>
                </div>
              ) : null
            )}
            {data.structured_output ? (
              <div>
                <dt className="text-zinc-500">Structured output</dt>
                <dd>
                  <pre className="mt-1 max-h-64 overflow-auto rounded bg-zinc-950 p-2 text-xs text-zinc-100">
                    {JSON.stringify(data.structured_output, null, 2)}
                  </pre>
                </dd>
              </div>
            ) : null}
          </dl>
        ) : null}
      </aside>
    </div>
  );
}
