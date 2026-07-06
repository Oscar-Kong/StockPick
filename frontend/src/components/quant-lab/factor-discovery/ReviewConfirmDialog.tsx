"use client";

import { useEffect, useRef } from "react";

export function ReviewConfirmDialog({
  open,
  title,
  description,
  confirmLabel,
  reason,
  onReasonChange,
  onConfirm,
  onCancel,
  loading,
  conflictMessage,
}: {
  open: boolean;
  title: string;
  description: string;
  confirmLabel: string;
  reason: string;
  onReasonChange: (v: string) => void;
  onConfirm: () => void;
  onCancel: () => void;
  loading?: boolean;
  conflictMessage?: string | null;
}) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (open) textareaRef.current?.focus();
  }, [open]);

  if (!open) return null;

  const disabled = loading || !reason.trim();

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="review-dialog-title"
      aria-describedby="review-dialog-desc"
    >
      <div className="w-full max-w-md rounded-lg border border-zinc-200 bg-white p-4 shadow-lg dark:border-zinc-700 dark:bg-zinc-900">
        <h2 id="review-dialog-title" className="text-base font-semibold">
          {title}
        </h2>
        <p id="review-dialog-desc" className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">
          {description}
        </p>
        <label className="mt-4 block text-sm font-medium" htmlFor="review-reason">
          Reason (required)
        </label>
        <textarea
          id="review-reason"
          ref={textareaRef}
          className="mt-1 w-full rounded border border-zinc-300 bg-white p-2 text-sm dark:border-zinc-600 dark:bg-zinc-950"
          rows={3}
          value={reason}
          onChange={(e) => onReasonChange(e.target.value)}
          disabled={loading}
        />
        {conflictMessage ? (
          <p className="mt-2 text-sm text-amber-700 dark:text-amber-300" role="alert" aria-live="polite">
            {conflictMessage}
          </p>
        ) : null}
        <div className="mt-4 flex justify-end gap-2">
          <button
            type="button"
            className="rounded border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-600"
            onClick={onCancel}
            disabled={loading}
          >
            Cancel
          </button>
          <button
            type="button"
            className="rounded bg-zinc-900 px-3 py-1.5 text-sm text-white disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900"
            onClick={onConfirm}
            disabled={disabled}
          >
            {loading ? "Submitting…" : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
