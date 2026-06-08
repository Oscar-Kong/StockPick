// Structured renderer for generated stock research reports.
"use client";

import { fmt, useTranslation } from "@/lib/i18n";
import type { RecommendationV2, SimilarSignalV2, StockResearchReport, ValuationV2 } from "@/lib/types";
import { AnalysisAlerts } from "./AnalysisAlerts";
import { RecommendationBlock } from "./RecommendationBlock";
import { SimilarSignalBlock } from "./SimilarSignalBlock";
import { ValuationBlock } from "./ValuationBlock";

interface ResearchReportProps {
  report: StockResearchReport | null;
  loading?: boolean;
  error?: string | null;
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-2 border-t border-zinc-800 pt-4">
      <h3 className="text-sm font-semibold">{title}</h3>
      <div className="text-sm text-zinc-400">{children}</div>
    </section>
  );
}

function formatCellValue(value: unknown): string {
  if (value == null) return "—";
  if (typeof value === "string") return value.replace(/_/g, " ");
  if (typeof value === "number") return String(value);
  return String(value);
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-4 text-xs">
      <span className="text-zinc-500">{label}</span>
      <span className="text-right font-medium text-zinc-200">{value}</span>
    </div>
  );
}

export function ResearchReport({ report, loading, error }: ResearchReportProps) {
  const { t } = useTranslation();

  if (loading) {
    return <p className="text-sm text-zinc-500">{t.report.generating}</p>;
  }
  if (error) {
    return <p className="text-sm text-red-600">{error}</p>;
  }
  if (!report || report.error) {
    return <p className="text-sm text-zinc-500">{report?.error ?? t.report.unavailable}</p>;
  }

  const o = report["1_overview"];
  const ind = report["2_industry_positioning"];
  const fund = report["3_fundamentals"];
  const tech = report["4_technical_structure"];
  const inst = report["5_institutional_liquidity"];
  const news = report["6_news_sentiment"];
  const zones = report["7_valuation_zones"];
  const outlook = report["8_risk_outlook"];
  const rec = report.recommendation;
  const val = report.valuation_analysis;
  const earnings = report.earnings_setup;
  const similar = report.similar_signal_backtest;

  const conclusionKey = outlook?.conclusion ?? "";
  const conclusionLabel =
    conclusionKey in t.report.conclusions
      ? t.report.conclusions[conclusionKey as keyof typeof t.report.conclusions]
      : outlook?.conclusion;

  const reportDate = report.generated_at?.slice(0, 16).replace("T", " ") ?? "—";
  const reportScore = report.quant_score?.toFixed(1) ?? "—";

  return (
    <div className="space-y-1">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs text-zinc-500">
          {fmt(t.report.header, { date: reportDate, score: reportScore })}
        </p>
        {report.data_quality_score != null && (
          <span className="text-xs text-zinc-500">
            {fmt(t.report.dataQuality, { pct: report.data_quality_score.toFixed(0) })}
          </span>
        )}
      </div>

      {rec && typeof rec === "object" && "recommendation" in rec && (
        <Section title={t.report.quantRec}>
          <RecommendationBlock data={rec as RecommendationV2} />
        </Section>
      )}

      {val && typeof val === "object" && "verdict" in val && (
        <Section title={t.report.valuationAnalysis}>
          <ValuationBlock data={val as ValuationV2} />
        </Section>
      )}

      {earnings && Object.keys(earnings).length > 0 && (
        <Section title={t.report.earningsSetup}>
          <div className="space-y-1">
            <Row
              label={t.report.nextEarnings}
              value={formatCellValue(
                earnings.next_earnings_days != null ? `${earnings.next_earnings_days}d` : null
              )}
            />
            <Row
              label={t.report.epsRev30d}
              value={
                earnings.eps_revision_30d_pct != null ? `${earnings.eps_revision_30d_pct}%` : "—"
              }
            />
            <Row
              label={t.report.revenueRev30d}
              value={
                earnings.revenue_revision_30d_pct != null
                  ? `${earnings.revenue_revision_30d_pct}%`
                  : "—"
              }
            />
            <Row label={t.report.analystUpgrades} value={formatCellValue(earnings.analyst_upgrades)} />
            <Row label={t.report.analystDowngrades} value={formatCellValue(earnings.analyst_downgrades)} />
            <Row
              label={t.report.lastSurprise}
              value={earnings.last_surprise_pct != null ? `${earnings.last_surprise_pct}%` : "—"}
            />
            <Row label={t.report.postEarningsDrift} value={formatCellValue(earnings.post_earnings_drift)} />
            <Row label={t.report.catalystScore} value={formatCellValue(earnings.catalyst_score)} />
          </div>
        </Section>
      )}

      {similar && typeof similar === "object" && "sample_n" in similar && (
        <Section title={t.report.similarSignal}>
          <SimilarSignalBlock data={similar as SimilarSignalV2} />
        </Section>
      )}

      {report.alerts && report.alerts.length > 0 && (
        <div className="py-2">
          <AnalysisAlerts alerts={report.alerts} />
        </div>
      )}

      <Section title={t.report.section1}>
        <div className="space-y-1">
          <Row label={t.report.company} value={o?.company_name ?? report.symbol} />
          <Row label={t.scan.sector} value={o?.sector ?? "—"} />
          <Row label={t.analysis.industry} value={o?.industry ?? "—"} />
          <Row label={t.common.price} value={o?.price != null ? `$${o.price.toFixed(2)}` : "—"} />
          <Row
            label={t.scan.marketCap}
            value={o?.market_cap != null ? `$${(o.market_cap / 1e9).toFixed(2)}B` : "—"}
          />
          <Row label={t.report.high52w} value={o?.high_52w != null ? `$${o.high_52w}` : "—"} />
          <Row label={t.report.low52w} value={o?.low_52w != null ? `$${o.low_52w}` : "—"} />
        </div>
        <p className="mt-2 text-xs leading-relaxed">{o?.business_summary}</p>
      </Section>

      <Section title={t.report.section2}>
        <div className="space-y-1">
          <Row label={t.report.industryGrowth} value={formatCellValue(ind?.industry_growth_stage)} />
          <Row label={t.report.competitivePosition} value={formatCellValue(ind?.competitive_position)} />
          <Row label={t.report.sectorStrength} value={formatCellValue(ind?.sector_strength_vs_market)} />
          <Row
            label={t.report.onMainTrend}
            value={ind?.sector_on_trend ? t.common.yes : t.common.no}
          />
        </div>
        <p className="mt-2 text-xs">{String(ind?.macro_background ?? "")}</p>
      </Section>

      <Section title={t.report.section3}>
        <div className="space-y-2">
          <p className="text-xs font-medium text-zinc-500">{t.report.valuation}</p>
          <Row label={t.scan.pe} value={fund?.valuation?.pe?.toFixed(1) ?? "—"} />
          <Row label="P/B" value={fund?.valuation?.pb?.toFixed(2) ?? "—"} />
          <p className="text-xs italic">{fund?.valuation?.pe_vs_history_note}</p>
          <p className="text-xs font-medium text-zinc-500">{t.report.profitability}</p>
          <Row
            label={t.report.roe}
            value={
              fund?.profitability?.roe != null
                ? `${(fund.profitability.roe * (fund.profitability.roe < 2 ? 100 : 1)).toFixed(1)}%`
                : "—"
            }
          />
          <Row
            label={t.report.grossMargin}
            value={
              fund?.profitability?.gross_margin != null
                ? `${(fund.profitability.gross_margin * 100).toFixed(1)}%`
                : "—"
            }
          />
          <p className="text-xs font-medium text-zinc-500">{t.report.growthYoy}</p>
          <Row
            label={t.report.revenue}
            value={
              fund?.growth?.revenue_yoy != null
                ? `${(fund.growth.revenue_yoy * 100).toFixed(1)}%`
                : "—"
            }
          />
          <Row
            label={t.report.earningsGrowth}
            value={
              fund?.growth?.earnings_yoy != null
                ? `${(fund.growth.earnings_yoy * 100).toFixed(1)}%`
                : "—"
            }
          />
        </div>
      </Section>

      <Section title={t.report.section4}>
        <div className="space-y-1">
          <Row label={t.report.weeklyTrend} value={formatCellValue(tech?.weekly_trend)} />
          <Row label={t.report.monthlyTrend} value={formatCellValue(tech?.monthly_trend)} />
          <Row label={t.report.ma200} value={formatCellValue(tech?.ma200_position)} />
          <Row
            label={t.report.majorSupport}
            value={tech?.major_support != null ? `$${tech.major_support}` : "—"}
          />
          <Row
            label={t.report.majorResistance}
            value={tech?.major_resistance != null ? `$${tech.major_resistance}` : "—"}
          />
          <Row
            label={t.report.nearSupport}
            value={tech?.support_near != null ? `$${tech.support_near}` : "—"}
          />
          <Row
            label={t.report.nearResistance}
            value={tech?.resistance_near != null ? `$${tech.resistance_near}` : "—"}
          />
          <Row label={t.report.volumePattern} value={formatCellValue(tech?.volume_signal)} />
        </div>
      </Section>

      <Section title={t.report.section5}>
        <div className="space-y-1">
          <Row
            label={t.report.institutionalPct}
            value={
              inst?.institutional_ownership_pct != null
                ? `${inst.institutional_ownership_pct}%`
                : "—"
            }
          />
          <Row label={t.report.flow30d} value={formatCellValue(inst?.capital_flow_30d)} />
        </div>
        <p className="mt-1 text-xs italic">{formatCellValue(inst?.institutional_activity_note)}</p>
      </Section>

      <Section title={t.report.section6}>
        <div className="space-y-1">
          <Row label={t.report.earningsDate} value={news?.earnings_date ?? "—"} />
          <Row label={t.report.sentiment} value={news?.market_sentiment} />
          <Row label={t.report.analystView} value={news?.analyst_consensus ?? "—"} />
          <Row label={t.report.priceTarget} value={news?.price_target_note ?? "—"} />
        </div>
        {news?.news_headlines && news.news_headlines.length > 0 && (
          <ul className="mt-2 list-inside list-disc text-xs">
            {news.news_headlines.map((h) => (
              <li key={h}>{h}</li>
            ))}
          </ul>
        )}
      </Section>

      <Section title={t.report.section7}>
        <div className="space-y-1">
          <Row label={t.report.currentZone} value={formatCellValue(zones?.current_zone)} />
          <Row label={t.report.buyZone} value={zones?.undervalued_buy_zone} />
          <Row label={t.report.holdZone} value={zones?.fair_value_hold_zone} />
          <Row label={t.report.reduceZone} value={zones?.overvalued_reduce_zone} />
        </div>
      </Section>

      <Section title={t.report.section8}>
        <ul className="list-inside list-disc text-xs">
          {outlook?.top_risks?.map((r, i) => (
            <li key={i}>{r}</li>
          ))}
        </ul>
        <p className="mt-2 text-sm font-medium">
          {t.report.conclusion} {conclusionLabel}
        </p>
        <p className="mt-1 text-xs">{outlook?.strategy_guidance}</p>
      </Section>
    </div>
  );
}
