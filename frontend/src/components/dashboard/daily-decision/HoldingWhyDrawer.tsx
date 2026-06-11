"use client";

import { useState } from "react";
import type { PortfolioDecisionItem } from "@/lib/types";
import { useTranslation } from "@/lib/i18n";
import { AppCard } from "@/components/ui/AppCard";
import { LabelCaps } from "@/components/ui/typography";

function ScoreRow({ label, value }: { label: string; value: string | number | null | undefined }) {
  return (
    <div className="flex items-center justify-between gap-3 py-2 text-sm">
      <span className="text-tertiary">{label}</span>
      <span className="finance-value font-medium text-zinc-100">{value ?? "—"}</span>
    </div>
  );
}

export function HoldingWhyDrawer({ item }: { item: PortfolioDecisionItem }) {
  const { t } = useTranslation();
  const [scoresOpen, setScoresOpen] = useState(false);
  const [rawOpen, setRawOpen] = useState(false);

  return (
    <AppCard variant="muted" className="space-y-4 p-4">
      <div>
        <LabelCaps>{t.home.dailyWhySuggestedAction}</LabelCaps>
        <p className="mt-2 text-sm leading-relaxed text-zinc-200">
          {item.suggested_action || t.home.dailyWhyNoAction}
        </p>
      </div>

      {item.reasons.length > 0 && (
        <div>
          <LabelCaps>{t.home.dailyWhyReasons}</LabelCaps>
          <ul className="mt-2 space-y-1.5 text-sm leading-relaxed text-secondary">
            {item.reasons.map((r) => (
              <li key={r} className="flex gap-2">
                <span className="text-zinc-600">·</span>
                <span>{r}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {item.risk_flags.length > 0 && (
        <div>
          <LabelCaps>{t.home.dailyWhyRiskFlags}</LabelCaps>
          <p className="mt-2 text-sm text-amber-300/90">{item.risk_flags.join(" · ")}</p>
        </div>
      )}

      <div>
        <button
          type="button"
          onClick={() => setScoresOpen((v) => !v)}
          className="text-xs font-medium text-tertiary hover:text-zinc-200"
        >
          {scoresOpen ? t.home.dailyHideScoreBreakdown : t.home.dailyShowScoreBreakdown}
        </button>
        {scoresOpen && (
          <div className="mt-2 divide-y divide-white/5 rounded-lg border border-white/5 px-3">
            <ScoreRow label={t.home.dailyDebugAlpha} value={item.alpha_score} />
            <ScoreRow label={t.home.dailyDebugMomentum} value={item.momentum_score} />
            <ScoreRow label={t.home.dailyDebugLiquidity} value={item.liquidity_score} />
            <ScoreRow label={t.home.dailyDebugRisk} value={item.risk_score ?? item.risk_index} />
            <ScoreRow label={t.home.dailyDebugDq} value={item.data_quality_score} />
            <ScoreRow
              label={t.portfolio.dailyColCurWt}
              value={item.current_weight != null ? `${item.current_weight}%` : null}
            />
            <ScoreRow
              label={t.portfolio.dailyColTgtWt}
              value={item.target_weight != null ? `${item.target_weight}%` : null}
            />
          </div>
        )}
      </div>

      <div>
        <button
          type="button"
          onClick={() => setRawOpen((v) => !v)}
          className="text-xs font-medium text-tertiary hover:text-zinc-200"
        >
          {rawOpen ? t.home.dailyHideRawDebug : t.home.dailyShowRawDebug}
        </button>
        {rawOpen && (
          <div className="mt-2 grid gap-0 rounded-lg border border-white/5 bg-zinc-950/50 px-3 sm:grid-cols-2">
            <ScoreRow label={t.home.dailyDebugBuyRaw} value={item.final_buy_raw} />
            <ScoreRow label={t.home.dailyDebugKeepRaw} value={item.final_keep_raw} />
            <ScoreRow label={t.home.dailyDebugSellRaw} value={item.final_sell_raw} />
            <ScoreRow label={t.home.dailyDebugOwPenalty} value={item.overweight_penalty} />
            <ScoreRow label={t.home.dailyDebugMissingPenalty} value={item.missing_data_penalty} />
            <ScoreRow
              label={t.home.dailyDebugStopLoss}
              value={item.stop_loss_trigger ? t.common.yes : t.common.no}
            />
          </div>
        )}
      </div>
    </AppCard>
  );
}
