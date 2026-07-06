import { request } from "../client";
import type {
  FactorPromotionCandidateDetail,
  FactorPromotionCandidateSummary,
  PromotionAuditHistoryResponse,
  PromotionEvidenceBundle,
  ShadowEvaluationRun,
} from "./types";

const BASE = "/api/v2/research/factor-discovery";

export async function fetchPromotionReadiness(signal?: AbortSignal) {
  return request(`${BASE}/promotion/readiness`, { signal });
}

export async function listPromotionCandidates(
  params: Record<string, string | number | undefined> = {},
  signal?: AbortSignal
): Promise<{ items: FactorPromotionCandidateSummary[]; total: number }> {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== "") qs.set(k, String(v));
  }
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  return request(`${BASE}/promotion-candidates${suffix}`, { signal });
}

export async function getPromotionCandidate(candidateId: string, signal?: AbortSignal): Promise<FactorPromotionCandidateDetail> {
  return request(`${BASE}/promotion-candidates/${encodeURIComponent(candidateId)}`, { signal });
}

export async function getPromotionEvidence(candidateId: string, signal?: AbortSignal): Promise<PromotionEvidenceBundle> {
  return request(`${BASE}/promotion-candidates/${encodeURIComponent(candidateId)}/evidence`, { signal });
}

export async function getPromotionAudit(candidateId: string, signal?: AbortSignal): Promise<PromotionAuditHistoryResponse> {
  return request(`${BASE}/promotion-candidates/${encodeURIComponent(candidateId)}/audit`, { signal });
}

export async function transitionPromotionCandidate(
  candidateId: string,
  body: { target_status: string; actor: string; reason: string; expected_evidence_bundle_hash?: string }
) {
  return request(`${BASE}/promotion-candidates/${encodeURIComponent(candidateId)}/transitions`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function requestShadowEvaluation(
  candidateId: string,
  body: { as_of_date: string; symbols: string[]; shadow_weight?: number; actor?: string }
): Promise<ShadowEvaluationRun> {
  return request(`${BASE}/promotion-candidates/${encodeURIComponent(candidateId)}/shadow-evaluations`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function listShadowEvaluations(candidateId: string, signal?: AbortSignal) {
  return request(`${BASE}/promotion-candidates/${encodeURIComponent(candidateId)}/shadow-evaluations`, { signal });
}

export async function explainPromotionCandidate(candidateId: string, signal?: AbortSignal) {
  return request(`${BASE}/promotion-candidates/${encodeURIComponent(candidateId)}/explain`, { method: "POST", signal });
}

export async function fetchExtendedStagingLatest(signal?: AbortSignal) {
  return request(`${BASE}/staging/extended-latest`, { signal });
}
