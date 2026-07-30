import type {
  Defect,
  DefectApi,
  DefectStatus,
  DefectUpdate,
  Regression,
  RegressionInput,
  Severity
} from "./types";


const JSON_HEADERS = { "Content-Type": "application/json" };


async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const response = await fetch(path, {
    headers: JSON_HEADERS,
    ...options
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail ?? "Defect request failed");
  }
  return response.json() as Promise<T>;
}


export const defectApi: DefectApi = {
  list: (status?: DefectStatus, severity?: Severity) => {
    const query = new URLSearchParams();
    if (status) query.set("status", status);
    if (severity) query.set("severity", severity);
    const suffix = query.size ? `?${query.toString()}` : "";
    return request<Defect[]>(`/api/defects${suffix}`);
  },
  get: (id) => request<Defect>(`/api/defects/${id}`),
  create: (input) =>
    request<Defect>("/api/defects", {
      method: "POST",
      headers: JSON_HEADERS,
      body: JSON.stringify(input)
    }),
  update: (id: string, input: DefectUpdate) =>
    request<Defect>(`/api/defects/${id}`, {
      method: "PUT",
      headers: JSON_HEADERS,
      body: JSON.stringify(input)
    }),
  transition: (id, targetStatus, resolutionNotes) =>
    request<Defect>(`/api/defects/${id}/status`, {
      method: "PUT",
      headers: JSON_HEADERS,
      body: JSON.stringify({
        target_status: targetStatus,
        resolution_notes: resolutionNotes
      })
    }),
  listRegressions: (id) =>
    request<Regression[]>(`/api/defects/${id}/regressions`),
  createRegression: (id: string, input: RegressionInput) =>
    request<Regression>(`/api/defects/${id}/regressions`, {
      method: "POST",
      headers: JSON_HEADERS,
      body: JSON.stringify(input)
    })
};
