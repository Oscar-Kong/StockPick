"use client";

import clsx from "clsx";
import { useTranslation } from "@/lib/i18n";

interface NotFinancialAdviceFooterProps {
  className?: string;
  llmNote?: boolean;
}

export function NotFinancialAdviceFooter({ className, llmNote = false }: NotFinancialAdviceFooterProps) {
  const { t } = useTranslation();
  return (
    <footer className={clsx("border-t border-zinc-800 pt-3 text-[11px] leading-relaxed text-zinc-500", className)}>
      {llmNote && <p className="mb-1 text-zinc-400">{t.analysis.llmDoesNotOverride}</p>}
      <p>{t.analysis.notFinancialAdvice}</p>
    </footer>
  );
}
