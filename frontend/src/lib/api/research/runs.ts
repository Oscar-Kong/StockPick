import type {
  ResearchRunCompareDetailResponse,
  ResearchRunDetailResponse,
  ResearchRunListItem,
  ResearchRunListResponse,
} from "../../types";
import { request } from "../client";

export type V2RequestOptions = { signal?: AbortSignal };

export function postResearchRunsBackfill(
  limit = 100,
  options?: V2RequestOptions,
): Promise<Record<string, unknown>> {
  return request(`/api/v2/research/runs/backfill?limit=${limit}`, {
    method: "POST",
    signal: options?.signal,
  });
}

export async function listResearchRuns(
  params: {
    run_type?: string;
    sleeve?: string;
    status?: string;
    verdict?: string;
    evidence_impact?: string;
    search?: string;
    date_from?: string;
    date_to?: string;
    include_archived?: boolean;
    offset?: number;
    limit?: number;
  } = {},
  options?: V2RequestOptions,
): Promise<ResearchRunListResponse> {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== "") qs.set(k, String(v));
  }
  return request(`/api/v2/research/runs?${qs.toString()}`, { signal: options?.signal });
}

export async function getResearchRunDetail(
  runId: string,
  refresh = false,
  options?: V2RequestOptions,
): Promise<ResearchRunDetailResponse> {
  return request(
    `/api/v2/research/runs/${encodeURIComponent(runId)}/detail?refresh=${refresh}`,
    { signal: options?.signal },
  );
}

export async function compareResearchRunsDetail(
  runIds: string[],
  options?: V2RequestOptions,
): Promise<ResearchRunCompareDetailResponse> {
  return request(
    `/api/v2/research/runs/compare/detail?run_ids=${encodeURIComponent(runIds.join(","))}`,
    { signal: options?.signal },
  );
}

export async function exportResearchRun(
  runId: string,
  format: "json" | "csv",
  options?: V2RequestOptions,
): Promise<unknown> {
  return request(
    `/api/v2/research/runs/${encodeURIComponent(runId)}/export?format=${format}`,
    { signal: options?.signal },
  );
}

export async function patchResearchRunNotes(
  runId: string,
  notes: string,
  options?: V2RequestOptions,
): Promise<ResearchRunListItem> {
  return request(`/api/v2/research/runs/${encodeURIComponent(runId)}/notes`, {
    method: "PATCH",
    body: JSON.stringify({ notes }),
    signal: options?.signal,
  });
}

export async function patchResearchRunArchive(
  runId: string,
  archived: boolean,
  options?: V2RequestOptions,
): Promise<ResearchRunListItem> {
  return request(`/api/v2/research/runs/${encodeURIComponent(runId)}/archive`, {
    method: "PATCH",
    body: JSON.stringify({ archived }),
    signal: options?.signal,
  });
}

export async function duplicateResearchRunExperiment(
  runId: string,
  options?: V2RequestOptions,
): Promise<{ experiment_id: string; run_id: string }> {
  return request(`/api/v2/research/runs/${encodeURIComponent(runId)}/duplicate-experiment`, {
    method: "POST",
    signal: options?.signal,
  });
}

export async function createResearchRunFollowUpIdea(
  runId: string,
  body: { title?: string; hypothesis?: string } = {},
  options?: V2RequestOptions,
): Promise<ResearchRunListItem> {
  return request(`/api/v2/research/runs/${encodeURIComponent(runId)}/follow-up-idea`, {
    method: "POST",
    body: JSON.stringify(body),
    signal: options?.signal,
  });
}
