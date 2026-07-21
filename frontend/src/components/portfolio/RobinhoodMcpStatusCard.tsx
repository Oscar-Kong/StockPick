"use client";

import { useCallback, useEffect, useState } from "react";
import {
  getRobinhoodMcpStatus,
  testRobinhoodMcpConnection,
  type RobinhoodMcpStatusResponse,
} from "@/lib/api/portfolio";
import { useTranslation } from "@/lib/i18n";
import { formatCurrency } from "@/lib/dailyDecisionUtils";
import { GhostButton, SecondaryButton } from "@/components/ui/buttons";

const DOCS_HREF = "/docs/ROBINHOOD_MCP.md";
const LOGIN_SCRIPT = "./scripts/robinhood-mcp-login.sh";

export function RobinhoodMcpStatusCard({
  authenticated,
  cash,
  compact = false,
  forceShow = false,
}: {
  authenticated?: boolean;
  cash?: number;
  compact?: boolean;
  /** Show even when connection looks healthy (user-opened troubleshoot). */
  forceShow?: boolean;
}) {
  const { t } = useTranslation();
  const [status, setStatus] = useState<RobinhoodMcpStatusResponse | null>(null);
  const [testing, setTesting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const loadStatus = useCallback(async () => {
    try {
      const next = await getRobinhoodMcpStatus(false);
      setStatus(next);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : t.portfolio.robinhoodMcpStatusFailed);
    }
  }, [t.portfolio.robinhoodMcpStatusFailed]);

  useEffect(() => {
    void loadStatus();
  }, [loadStatus]);

  const runTest = async () => {
    setTesting(true);
    setError(null);
    try {
      const next = await testRobinhoodMcpConnection();
      setStatus(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : t.portfolio.robinhoodMcpTestFailed);
    } finally {
      setTesting(false);
    }
  };

  const loginScript = status?.login_script || LOGIN_SCRIPT;
  const probe = status?.probe;
  const isAuthed = status?.authenticated ?? authenticated;
  const needsReauth = Boolean(status?.token_expired || probe?.needs_reauth || !isAuthed);

  const copyLogin = async () => {
    try {
      await navigator.clipboard.writeText(loginScript);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      setCopied(false);
    }
  };

  // Parent decides visibility; forceShow is reserved for explicit troubleshoot expand.
  void forceShow;

  return (
    <div
      className={
        compact
          ? "rounded-xl border border-zinc-800/80 bg-zinc-950/50 px-4 py-3 text-left"
          : "mx-auto mt-6 max-w-lg rounded-xl border border-zinc-800/80 bg-zinc-950/50 px-4 py-4 text-left"
      }
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-zinc-100">{t.portfolio.robinhoodMcpDiagTitle}</h3>
          <p className="mt-1 text-xs text-secondary">{t.portfolio.robinhoodMcpDiagSubtitle}</p>
        </div>
        <SecondaryButton size="sm" onClick={() => void runTest()} disabled={testing} className="rounded-lg">
          {testing ? t.portfolio.robinhoodMcpTesting : t.portfolio.robinhoodMcpTest}
        </SecondaryButton>
      </div>

      <dl className="mt-3 grid gap-1.5 text-xs text-secondary sm:grid-cols-2">
        <div className="flex justify-between gap-2 sm:block">
          <dt>{t.portfolio.robinhoodLiveStatus}</dt>
          <dd className={isAuthed && !needsReauth ? "text-buy" : "text-amber-200"}>
            {needsReauth
              ? t.portfolio.robinhoodLiveNotConnected
              : isAuthed
                ? t.portfolio.robinhoodLiveConnected
                : t.portfolio.robinhoodLiveNotConnected}
          </dd>
        </div>
        {cash != null && (
          <div className="flex justify-between gap-2 sm:block">
            <dt>{t.portfolio.robinhoodMcpCash}</dt>
            <dd className="finance-value text-zinc-200">{formatCurrency(cash)}</dd>
          </div>
        )}
        {probe && (
          <>
            <div className="flex justify-between gap-2 sm:col-span-2 sm:block">
              <dt>{t.portfolio.robinhoodMcpProbe}</dt>
              <dd className={probe.ok ? "text-buy" : "text-negative"}>
                {probe.message || (probe.ok ? t.portfolio.robinhoodMcpProbeOk : t.portfolio.robinhoodMcpProbeFail)}
                {probe.latency_ms != null ? ` · ${probe.latency_ms}ms` : ""}
              </dd>
            </div>
            {probe.ok && (
              <div className="flex justify-between gap-2 sm:col-span-2 sm:block">
                <dt>{t.portfolio.robinhoodMcpProbeDetail}</dt>
                <dd className="finance-value text-zinc-200">
                  {t.portfolio.robinhoodMcpProbeCounts
                    .replace("{positions}", String(probe.holdings_count ?? 0))
                    .replace("{cash}", formatCurrency(Number(probe.cash ?? 0)))
                    .replace("{equity}", formatCurrency(Number(probe.equity_value ?? 0)))}
                </dd>
              </div>
            )}
          </>
        )}
      </dl>

      {(error || probe?.error) && (
        <p className="mt-2 text-xs text-negative">{error || probe?.error}</p>
      )}

      <div className="mt-3 rounded-lg border border-zinc-800/80 bg-zinc-900/60 px-3 py-2">
        <p className="text-[11px] font-medium uppercase tracking-wide text-tertiary">
          {t.portfolio.robinhoodMcpAuthorizeLabel}
        </p>
        <code className="mt-1 block break-all text-xs text-zinc-100">{loginScript}</code>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <GhostButton size="sm" onClick={() => void copyLogin()} className="rounded-lg px-2 py-1 text-xs">
            {copied ? t.portfolio.robinhoodMcpCopied : t.portfolio.robinhoodMcpCopyScript}
          </GhostButton>
          <a
            href="https://github.com/Oscar-Kong/StockPick/blob/main/docs/ROBINHOOD_MCP.md"
            target="_blank"
            rel="noreferrer"
            className="text-xs font-medium text-primary hover:underline"
          >
            {t.portfolio.robinhoodMcpDocsLink}
          </a>
        </div>
        <p className="mt-2 text-xs leading-relaxed text-secondary">{t.portfolio.robinhoodLiveLoginHint}</p>
      </div>
    </div>
  );
}

// Keep unused DOCS_HREF for local doc path reference in comments / future in-app docs route.
void DOCS_HREF;
