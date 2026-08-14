"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { getDailyDashboard, runDailyDecisionNow } from "@/lib/api/portfolio";

export type DailyDashboardErrorMessages = {
  loadFailed: string;
  runFailed: string;
};

export function useDailyDashboard(messages?: DailyDashboardErrorMessages) {
  const messagesRef = useRef(messages);
  useEffect(() => {
    messagesRef.current = messages;
  }, [messages]);
  const [data, setData] = useState<Awaited<ReturnType<typeof getDailyDashboard>> | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const resolveError = useCallback(
    (key: keyof DailyDashboardErrorMessages, err: unknown) => {
      if (err instanceof Error && err.message) return err.message;
      return messagesRef.current?.[key] ?? "Request failed";
    },
    [],
  );

  const load = useCallback(async (opts?: { silent?: boolean }) => {
    if (!opts?.silent) setLoading(true);
    setError(null);
    try {
      const dashboard = await getDailyDashboard();
      setData(dashboard);
    } catch (err) {
      setError(resolveError("loadFailed", err));
    } finally {
      if (!opts?.silent) setLoading(false);
    }
  }, [resolveError]);

  const runDecision = useCallback(async () => {
    setRunning(true);
    setError(null);
    try {
      await runDailyDecisionNow();
      await load({ silent: true });
    } catch (err) {
      setError(resolveError("runFailed", err));
    } finally {
      setRunning(false);
    }
  }, [load, resolveError]);

  useEffect(() => {
    void load();
  }, [load]);

  return {
    data,
    loading,
    running,
    error,
    load,
    runDecision,
    setError,
    setData,
  };
}
