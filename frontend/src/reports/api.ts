import type { Archive, Report, ReportApi } from "./types";


const JSON_HEADERS = { "Content-Type": "application/json" };


async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(path, { headers: JSON_HEADERS, ...options });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail ?? "Report request failed");
  }
  return response.json() as Promise<T>;
}


export const reportApi: ReportApi = {
  listProjectReports: (projectId) =>
    request<Report[]>(`/api/test-projects/${projectId}/reports`),
  listRunReports: (runId) =>
    request<Report[]>(`/api/test-runs/${runId}/reports`),
  generateReport: (runId, title, mode) =>
    request<Report>(`/api/test-runs/${runId}/reports`, {
      method: "POST",
      body: JSON.stringify({ title, mode })
    }),
  getReport: (reportId) => request<Report>(`/api/reports/${reportId}`),
  createArchive: (reportId) =>
    request<Archive>(`/api/reports/${reportId}/archive`, {
      method: "POST"
    }),
  getReportArchive: (reportId) =>
    request<Archive>(`/api/reports/${reportId}/archive`),
  getArchive: (archiveId) =>
    request<Archive>(`/api/archives/${archiveId}`),
  reportDownloadUrl: (reportId) => `/api/reports/${reportId}/download`,
  archiveDownloadUrl: (archiveId) => `/api/archives/${archiveId}/download`
};
