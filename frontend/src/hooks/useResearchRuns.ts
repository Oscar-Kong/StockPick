"use client";

import { useCallback, useEffect, useState } from "react";
import {
  compareResearchRunsDetail,
  getResearchRunDetail,
  listResearchRuns,
} from "@/lib/api/research/runs";
import { parseApiError } from "@/lib/apiError";
import type {
  Bucket,
  ResearchRunCompareDetailResponse,
  ResearchRunDetailResponse,
  ResearchRunListItem,
} from "@/lib/types";

export type ResearchRunListFilters = {
  sleeve: Bucket;
  search?: string;
  run_type?: string;
  verdict?: string;
  evidence_impact?: string;
  status?: string;
  offset?: number;
  limit?: number;
};

export function useResearchRunList(
  filters: ResearchRunListFilters,
  options: { enabled?: boolean; loadFailed: string },
) {
  const {
    sleeve,
    search = "",
    run_type = "",
    verdict = "",
    evidence_impact = "",
    status = "",
    offset = 0,
    limit = 20,
  } = filters;

  const [runs, setRuns] = useState<ResearchRunListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await listResearchRuns({
        sleeve,
        search: search.trim() || undefined,
        run_type: run_type || undefined,
        verdict: verdict || undefined,
        evidence_impact: evidence_impact || undefined,
        status: status || undefined,
        offset,
        limit,
      });
      setRuns(res.runs);
      setTotal(res.total);
    } catch (e) {
      setRuns([]);
      setError(parseApiError(e, options.loadFailed));
    } finally {
      setLoading(false);
    }
  }, [
    sleeve,
    search,
    run_type,
    verdict,
    evidence_impact,
    status,
    offset,
    limit,
    options.loadFailed,
  ]);

  useEffect(() => {
    if (options.enabled === false) {
      setLoading(false);
      return;
    }
    const ac = new AbortController();
    let active = true;
    setLoading(true);
    setError(null);
    listResearchRuns(
      {
        sleeve,
        search: search.trim() || undefined,
        run_type: run_type || undefined,
        verdict: verdict || undefined,
        evidence_impact: evidence_impact || undefined,
        status: status || undefined,
        offset,
        limit,
      },
      { signal: ac.signal },
    )
      .then((res) => {
        if (!active) return;
        setRuns(res.runs);
        setTotal(res.total);
      })
      .catch((e) => {
        if (!active) return;
        if (e instanceof DOMException && e.name === "AbortError") return;
        setRuns([]);
        setError(parseApiError(e, options.loadFailed));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
      ac.abort();
    };
  }, [
    sleeve,
    search,
    run_type,
    verdict,
    evidence_impact,
    status,
    offset,
    limit,
    options.enabled,
    options.loadFailed,
  ]);

  return { runs, total, loading, error, reload, setError };
}

export function useResearchRunDetail(runId: string | null, loadFailed: string) {
  const [detail, setDetail] = useState<ResearchRunDetailResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    if (!runId) {
      setDetail(null);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const row = await getResearchRunDetail(runId);
      setDetail(row);
    } catch (e) {
      setDetail(null);
      setError(parseApiError(e, loadFailed));
    } finally {
      setLoading(false);
    }
  }, [runId, loadFailed]);

  useEffect(() => {
    if (!runId) {
      setDetail(null);
      setLoading(false);
      return;
    }
    const ac = new AbortController();
    let active = true;
    setLoading(true);
    setError(null);
    getResearchRunDetail(runId, false, { signal: ac.signal })
      .then((row) => {
        if (active) setDetail(row);
      })
      .catch((e) => {
        if (!active) return;
        if (e instanceof DOMException && e.name === "AbortError") return;
        setDetail(null);
        setError(parseApiError(e, loadFailed));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
      ac.abort();
    };
  }, [runId, loadFailed]);

  return { detail, loading, error, reload, setDetail };
}

export function useResearchRunCompare(compareIds: string | null, loadFailed: string) {
  const [compare, setCompare] = useState<ResearchRunCompareDetailResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!compareIds) {
      setCompare(null);
      setLoading(false);
      return;
    }
    const ids = compareIds.split(",").filter(Boolean);
    if (ids.length < 2) {
      setCompare(null);
      setLoading(false);
      return;
    }
    const ac = new AbortController();
    let active = true;
    setLoading(true);
    setError(null);
    compareResearchRunsDetail(ids, { signal: ac.signal })
      .then((row) => {
        if (active) setCompare(row);
      })
      .catch((e) => {
        if (!active) return;
        if (e instanceof DOMException && e.name === "AbortError") return;
        setError(parseApiError(e, loadFailed));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
      ac.abort();
    };
  }, [compareIds, loadFailed]);

  return { compare, loading, error };
}
