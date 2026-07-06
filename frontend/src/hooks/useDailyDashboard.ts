"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  getDailyDashboard,
  getHomeRefreshStatus,
  refreshHomeData,
  runDailyDecisionNow,
} from "@/lib/api/portfolio";

const POLL_MS = 5000;

export type DailyDashboardErrorMessages = {
  loadFailed: string;
  refreshFailed: string;
  runFailed: string;
};

export function useDailyDashboard(messages?: DailyDashboardErrorMessages) {
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const messagesRef = useRef(messages);
  useEffect(() => {
    messagesRef.current = messages;
  }, [messages]);
  const [data, setData] = useState<Awaited<ReturnType<typeof getDailyDashboard>> | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [refreshJobId, setRefreshJobId] = useState<string | null>(null);

  const resolveError = useCallback(
    (key: keyof DailyDashboardErrorMessages, err: unknown) => {
      if (err instanceof Error && err.message) return err.message;
      return messagesRef.current?.[key] ?? "Request failed";
    },
    [],
  );

  const load = useCallback(async (opts?: { silent?: boolean; skipAutoRefresh?: boolean }) => {
    if (!opts?.silent) setLoading(true);
    setError(null);
    try {
      const dashboard = await getDailyDashboard(
        opts?.silent || opts?.skipAutoRefresh ? { skipAutoRefresh: true } : undefined,
      );
      setData(dashboard);
      const f = dashboard.freshness;
      const inProgress = Boolean(f?.refresh_in_progress || f?.overall_status === "updating");
      if (f?.refresh_job_id) {
        setRefreshJobId(f.refresh_job_id);
      } else if (!inProgress) {
        setRefreshJobId(null);
      }
      setRefreshing(inProgress);
    } catch (err) {
      setError(resolveError("loadFailed", err));
    } finally {
      if (!opts?.silent) setLoading(false);
    }
  }, [resolveError]);

  const refresh = useCallback(async (force = false) => {
    setRefreshing(true);
    setError(null);
    try {
      const res = await refreshHomeData(force);
      if (res.job_id) {
        setRefreshJobId(res.job_id);
      } else if (res.status === "running") {
        setRefreshJobId(null);
      } else if (res.status === "completed") {
        await load({ silent: true, skipAutoRefresh: true });
        setRefreshing(false);
        setRefreshJobId(null);
      }
    } catch (err) {
      setError(resolveError("refreshFailed", err));
      setRefreshing(false);
      setRefreshJobId(null);
    }
  }, [load, resolveError]);

  const runDecision = useCallback(async () => {
    setRunning(true);
    setError(null);
    try {
      await runDailyDecisionNow();
      await load();
    } catch (err) {
      setError(resolveError("runFailed", err));
    } finally {
      setRunning(false);
    }
  }, [load, resolveError]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!refreshJobId && !refreshing) {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
      return;
    }

    const poll = async () => {
      if (refreshJobId) {
        try {
          const status = await getHomeRefreshStatus(refreshJobId);
          if (status.status === "completed" || status.status === "failed") {
            setRefreshJobId(null);
            setRefreshing(false);
            await load({ silent: true, skipAutoRefresh: true });
          }
        } catch {
          setRefreshJobId(null);
          await load({ silent: true, skipAutoRefresh: true });
        }
      } else if (refreshing) {
        await load({ silent: true, skipAutoRefresh: true });
      }
    };

    void poll();
    pollRef.current = setInterval(() => void poll(), POLL_MS);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [refreshJobId, refreshing, load]);

  return {
    data,
    loading,
    running,
    refreshing,
    error,
    refreshJobId,
    load,
    refresh,
    runDecision,
    setError,
    setData,
  };
}
