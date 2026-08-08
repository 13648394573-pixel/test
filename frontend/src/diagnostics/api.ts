import type { DiagnosticApi, DiagnosticInput, DiagnosticSession } from "./types";

const JSON_HEADERS = { "Content-Type": "application/json" };

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(path, { headers: JSON_HEADERS, ...options });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail ?? "Diagnostic request failed");
  }
  return response.json() as Promise<T>;
}

export const diagnosticApi: DiagnosticApi = {
  create: (resultId: string, input: DiagnosticInput) =>
    request<DiagnosticSession>(`/api/run-results/${resultId}/diagnostics`, {
      method: "POST", headers: JSON_HEADERS, body: JSON.stringify(input)
    }),
  list: (resultId: string) => request<DiagnosticSession[]>(`/api/run-results/${resultId}/diagnostics`),
  get: (sessionId: string) => request<DiagnosticSession>(`/api/diagnostics/${sessionId}`)
};
