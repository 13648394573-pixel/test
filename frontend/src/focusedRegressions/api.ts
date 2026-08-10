import type {
  FocusedRegressionApi,
  FocusedRegressionInput,
  FocusedRegressionRun
} from "./types";


const JSON_HEADERS = { "Content-Type": "application/json" };


async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const response = await fetch(path, { headers: JSON_HEADERS, ...options });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail ?? "Focused regression request failed");
  }
  return response.json() as Promise<T>;
}


export const focusedRegressionApi: FocusedRegressionApi = {
  create: (defectId: string, input: FocusedRegressionInput) =>
    request<FocusedRegressionRun>(
      `/api/defects/${defectId}/focused-regression-runs`,
      {
        method: "POST",
        headers: JSON_HEADERS,
        body: JSON.stringify(input)
      }
    ),
  listForDefect: (defectId: string) =>
    request<FocusedRegressionRun[]>(
      `/api/defects/${defectId}/focused-regression-runs`
    ),
  getByRun: (runId: string) =>
    request<FocusedRegressionRun>(
      `/api/focused-regression-runs/${runId}`
    )
};
