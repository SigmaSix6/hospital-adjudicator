import type { CaseDetail, CaseListItem, Health, LlmCallsResponse, LlmMode, ReviewResult } from "./types";

export class ApiError extends Error {
  constructor(message: string, public status: number) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`/api${path}`, { cache: "no-store", ...init });
  } catch {
    throw new ApiError("Could not reach the UI server.", 0);
  }
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {}
    throw new ApiError(detail, res.status);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => request<Health>("/health"),
  cases: () => request<CaseListItem[]>("/cases"),
  caseDetail: (id: string) => request<CaseDetail>(`/cases/${id}`),
  latestReview: async (id: string): Promise<ReviewResult | null> => {
    try {
      return await request<ReviewResult>(`/cases/${id}/reviews/latest`);
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) return null;
      throw e;
    }
  },
  review: (id: string, mode: LlmMode, useCache: boolean) =>
    request<ReviewResult>(
      `/cases/${id}/review?llm_mode=${mode}&use_cache=${useCache}&run_label=ui`,
      { method: "POST" },
    ),
  llmCalls: () => request<LlmCallsResponse>("/llm-calls?limit=1"),
};
