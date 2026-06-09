"use client";

import { useTranslation } from "@/lib/i18n";

/** Shown where model/weight changes could affect future scans — no auto-apply in UI. */
export function ApplyChangesNotice({ hasApplyAction = false }: { hasApplyAction?: boolean }) {
  const { t } = useTranslation();
  return (
    <p className="rounded-md border border-amber-900/40 bg-amber-950/20 px-3 py-2 text-xs text-amber-200/90">
      {hasApplyAction ? t.product.applyChangesWarning : t.product.manualReviewRequired}
    </p>
  );
}

interface ApplyChangesConfirmProps {
  label: string;
  onConfirm: () => void;
  disabled?: boolean;
}

/** Gate risky actions behind explicit confirmation (future apply endpoints). */
export function ApplyChangesConfirm({ label, onConfirm, disabled }: ApplyChangesConfirmProps) {
  const { t } = useTranslation();

  const handleClick = () => {
    const ok = window.confirm(`${t.product.applyChangesWarning}\n\n${t.product.applyChangesConfirmPrompt}`);
    if (ok) onConfirm();
  };

  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={disabled}
      className="btn-primary px-3 py-1.5 text-sm disabled:opacity-50"
    >
      {label}
    </button>
  );
}
