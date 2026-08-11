import type { RunComparison, RunHistoryApi, RunHistoryFilters, RunHistoryPage } from "./types";


async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(path, options);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail ?? "Run history request failed");
  }
  return response.json() as Promise<T>;
}


export const runHistoryApi: RunHistoryApi = {
  search: (filters: RunHistoryFilters) => {
    const query = new URLSearchParams();
    Object.entries(filters).forEach(([key, value]) => {
      if (value !== undefined && value !== "") query.set(key, String(value));
    });
    return request<RunHistoryPage>(`/api/test-runs?${query.toString()}`);
  },
  compare: (runIds: string[]) => request<RunComparison>("/api/test-runs/compare", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ run_ids: runIds })
  })
};
