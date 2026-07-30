import type {
  Evidence,
  EvidenceCategory,
  ResultDraftInput,
  RunResult,
  TestExecutionApi,
  TestProject,
  TestRun
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
    throw new Error(body.detail ?? "Test execution request failed");
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}


export const testExecutionApi: TestExecutionApi = {
  listProjects: () => request<TestProject[]>("/api/test-projects"),
  createProject: (input) =>
    request<TestProject>("/api/test-projects", {
      method: "POST",
      headers: JSON_HEADERS,
      body: JSON.stringify(input)
    }),
  updateProject: (id, input) =>
    request<TestProject>(`/api/test-projects/${id}`, {
      method: "PUT",
      headers: JSON_HEADERS,
      body: JSON.stringify(input)
    }),
  deleteProject: (id) =>
    request<void>(`/api/test-projects/${id}`, {
      method: "DELETE",
      headers: JSON_HEADERS
    }),
  createRun: (projectId, deviceSourceId) =>
    request<TestRun>(`/api/test-projects/${projectId}/runs`, {
      method: "POST",
      headers: JSON_HEADERS,
      body: JSON.stringify({ device_source_id: deviceSourceId })
    }),
  getRun: (runId) => request<TestRun>(`/api/test-runs/${runId}`),
  listRuns: (projectId) =>
    request<TestRun[]>(`/api/test-projects/${projectId}/runs`),
  updateResult: (
    runId: string,
    resultId: string,
    input: ResultDraftInput
  ) =>
    request<RunResult>(`/api/test-runs/${runId}/results/${resultId}`, {
      method: "PUT",
      headers: JSON_HEADERS,
      body: JSON.stringify(input)
    }),
  lockResult: (runId, resultId) =>
    request<RunResult>(
      `/api/test-runs/${runId}/results/${resultId}/lock`,
      { method: "POST", headers: JSON_HEADERS }
    ),
  listResultEvidence: (resultId) =>
    request<Evidence[]>(`/api/run-results/${resultId}/evidences`),
  uploadResultEvidence: (
    resultId: string,
    category: EvidenceCategory,
    file: File,
    description: string | null
  ) => {
    const form = new FormData();
    form.set("category", category);
    form.set("file", file);
    if (description) form.set("description", description);
    return request<Evidence>(`/api/run-results/${resultId}/evidences`, {
      method: "POST",
      headers: {},
      body: form
    });
  },
  deleteEvidence: (evidenceId) =>
    request<void>(`/api/evidences/${evidenceId}`, {
      method: "DELETE",
      headers: JSON_HEADERS
    }),
  evidenceDownloadUrl: (evidenceId) =>
    `/api/evidences/${evidenceId}/download`
};
