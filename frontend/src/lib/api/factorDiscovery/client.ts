import { request } from "../client";
import type {
  LlmCandidateItem,
  MiningEventItem,
  MiningMutationEnvelope,
  MiningReadiness,
  MiningSessionDetail,
  MiningSessionListItem,
  ResearchFamilyItem,
} from "./types";

const BASE = "/api/v2/research/factor-discovery";

export async function fetchMiningReadiness(signal?: AbortSignal): Promise<MiningReadiness> {
  return request(`${BASE}/mining/readiness`, { signal });
}

export async function listMiningSessions(
  params: Record<string, string | number | boolean | undefined> = {},
  signal?: AbortSignal
): Promise<{ items: MiningSessionListItem[]; limit: number; offset: number }> {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== "") qs.set(k, String(v));
  }
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  return request(`${BASE}/mining/sessions${suffix}`, { signal });
}

export async function getMiningSession(sessionId: string, signal?: AbortSignal): Promise<MiningSessionDetail> {
  return request(`${BASE}/mining/sessions/${encodeURIComponent(sessionId)}`, { signal });
}

export async function getMiningEvents(sessionId: string, signal?: AbortSignal): Promise<{ items: MiningEventItem[] }> {
  return request(`${BASE}/mining/sessions/${encodeURIComponent(sessionId)}/events`, { signal });
}

export async function getMiningSummary(sessionId: string, signal?: AbortSignal): Promise<Record<string, unknown>> {
  return request(`${BASE}/mining/sessions/${encodeURIComponent(sessionId)}/summary`, { signal });
}

export async function listResearchFamilies(signal?: AbortSignal): Promise<{ items: ResearchFamilyItem[] }> {
  return request(`${BASE}/families`, { signal });
}

export async function createResearchFamily(body: Record<string, unknown>): Promise<{ family_id: string }> {
  return request(`${BASE}/families`, { method: "POST", body: JSON.stringify(body) });
}

export async function createMiningSession(body: Record<string, unknown>): Promise<{ session_id: string; state_version: number }> {
  return request(`${BASE}/mining/sessions`, { method: "POST", body: JSON.stringify(body) });
}

type MutationBody = {
  actor?: string;
  reason?: string;
  expected_state_version: number;
  resume_to?: string;
  maximum_steps?: number;
};

function postMutation(path: string, body: MutationBody): Promise<MiningMutationEnvelope> {
  return request(path, { method: "POST", body: JSON.stringify(body) });
}

export function authorizeMiningSession(sessionId: string, body: MutationBody) {
  return postMutation(`${BASE}/mining/sessions/${encodeURIComponent(sessionId)}/authorize`, body);
}

export function startMiningSession(sessionId: string, body: MutationBody) {
  return postMutation(`${BASE}/mining/sessions/${encodeURIComponent(sessionId)}/start`, body);
}

export function advanceMiningSession(sessionId: string, body: MutationBody) {
  return postMutation(`${BASE}/mining/sessions/${encodeURIComponent(sessionId)}/advance`, body);
}

export function pauseMiningSession(sessionId: string, body: MutationBody) {
  return postMutation(`${BASE}/mining/sessions/${encodeURIComponent(sessionId)}/pause`, body);
}

export function resumeMiningSession(sessionId: string, body: MutationBody) {
  return postMutation(`${BASE}/mining/sessions/${encodeURIComponent(sessionId)}/resume`, body);
}

export function cancelMiningSession(sessionId: string, body: MutationBody) {
  return postMutation(`${BASE}/mining/sessions/${encodeURIComponent(sessionId)}/cancel`, body);
}

export function approveHypothesis(sessionId: string, candidateId: string, body: MutationBody) {
  return postMutation(
    `${BASE}/mining/sessions/${encodeURIComponent(sessionId)}/hypotheses/${encodeURIComponent(candidateId)}/approve`,
    body
  );
}

export function rejectHypothesis(sessionId: string, candidateId: string, body: MutationBody) {
  return postMutation(
    `${BASE}/mining/sessions/${encodeURIComponent(sessionId)}/hypotheses/${encodeURIComponent(candidateId)}/reject`,
    body
  );
}

export function approveFormula(sessionId: string, candidateId: string, body: MutationBody) {
  return postMutation(
    `${BASE}/mining/sessions/${encodeURIComponent(sessionId)}/formulas/${encodeURIComponent(candidateId)}/approve`,
    body
  );
}

export function rejectFormula(sessionId: string, candidateId: string, body: MutationBody) {
  return postMutation(
    `${BASE}/mining/sessions/${encodeURIComponent(sessionId)}/formulas/${encodeURIComponent(candidateId)}/reject`,
    body
  );
}

export function approveRevision(sessionId: string, candidateId: string, body: MutationBody) {
  return postMutation(
    `${BASE}/mining/sessions/${encodeURIComponent(sessionId)}/revisions/${encodeURIComponent(candidateId)}/approve`,
    body
  );
}

export function rejectRevision(sessionId: string, candidateId: string, body: MutationBody) {
  return postMutation(
    `${BASE}/mining/sessions/${encodeURIComponent(sessionId)}/revisions/${encodeURIComponent(candidateId)}/reject`,
    body
  );
}

export async function listLlmCandidates(
  researchFamilyId: string,
  candidateType?: string,
  signal?: AbortSignal
): Promise<{ items: LlmCandidateItem[] }> {
  const qs = new URLSearchParams({ research_family_id: researchFamilyId });
  if (candidateType) qs.set("candidate_type", candidateType);
  return request(`${BASE}/llm/candidates?${qs.toString()}`, { signal });
}

export async function getLlmInteraction(interactionId: string, signal?: AbortSignal): Promise<Record<string, unknown>> {
  return request(`${BASE}/llm/interactions/${encodeURIComponent(interactionId)}`, { signal });
}

export async function fetchReviewQueue(
  params: Record<string, string | number | boolean | undefined> = {},
  signal?: AbortSignal
): Promise<{ items: import("./types").ReviewQueueItem[]; total: number }> {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== "") qs.set(k, String(v));
  }
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  return request(`${BASE}/mining/review-queue${suffix}`, { signal });
}

export async function getHypothesisCandidateDetail(candidateId: string, signal?: AbortSignal) {
  return request(`${BASE}/candidates/hypotheses/${encodeURIComponent(candidateId)}`, { signal });
}

export async function getFormulaCandidateDetail(candidateId: string, signal?: AbortSignal) {
  return request(`${BASE}/candidates/formulas/${encodeURIComponent(candidateId)}`, { signal });
}

export async function getRevisionCandidateDetail(candidateId: string, signal?: AbortSignal) {
  return request(`${BASE}/candidates/revisions/${encodeURIComponent(candidateId)}`, { signal });
}

export async function getValidationResultByArtifact(artifactId: string, signal?: AbortSignal) {
  return request(`${BASE}/artifacts/${encodeURIComponent(artifactId)}/validation-result`, { signal });
}

export async function getValidationResultByRun(runId: string, signal?: AbortSignal) {
  return request(`${BASE}/runs/${encodeURIComponent(runId)}/validation-result`, { signal });
}

export async function listFactorRegistry(
  params: Record<string, string | number | boolean | undefined> = {},
  signal?: AbortSignal
): Promise<{ items: import("./types").FactorRegistryItem[]; total: number }> {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== "") qs.set(k, String(v));
  }
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  return request(`${BASE}/factors${suffix}`, { signal });
}

export async function getFactorRegistryDetail(factorId: string, signal?: AbortSignal) {
  return request(`${BASE}/factors/${encodeURIComponent(factorId)}`, { signal });
}
