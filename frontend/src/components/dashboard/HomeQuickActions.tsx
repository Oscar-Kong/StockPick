"use client";

import { useTranslation } from "@/lib/i18n";
import Link from "next/link";

export function HomeQuickActions() {
  const { t } = useTranslation();
  const actions = [
    { href: "/scan", label: t.home.actionRunScan },
    { href: "/workspace", label: t.home.actionAnalyze },
    { href: "/portfolio", label: t.home.actionPortfolio },
    { href: "/quant-lab", label: t.home.actionQuantLab },
    { href: "/library", label: t.home.actionLibrary },
  ];

  return (
    <section className="surface-card p-4">
      <h2 className="mb-3 text-sm font-semibold text-zinc-200">{t.home.quickActions}</h2>
      <div className="flex flex-wrap gap-2">
        {actions.map((a) => (
          <Link
            key={a.href}
            href={a.href}
            className="rounded-lg border border-zinc-700 px-3 py-2 text-xs font-medium text-zinc-300 transition hover:border-[#00c805]/40 hover:bg-[#00c805]/10 hover:text-[#7dff8e]"
          >
            {a.label}
          </Link>
        ))}
      </div>
    </section>
  );
}
