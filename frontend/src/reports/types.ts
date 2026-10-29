export interface ReportSummary {
  total: number;
  pass: number;
  fail: number;
  blocked: number;
  defects: number;
}

export interface Archive {
  id: string;
  archive_no: string;
  report_id: string;
  project_id: string;
  manifest_version: number;
  manifest_snapshot: Record<string, unknown>;
  archive_storage_path: string;
  archive_sha256: string;
  archive_file_size: number;
  archived_at: string;
  created_at: string;
}

export interface Report {
  id: string;
  report_no: string;
  project_id: string;
  test_run_id: string;
  report_version: number;
  title: string;
  snapshot_version: number;
  report_snapshot: {
    summary: ReportSummary;
    [key: string]: unknown;
  };
  html_storage_path: string;
  html_sha256: string;
  html_file_size: number;
  generated_at: string;
  created_at: string;
  archive: Archive | null;
}

export interface ReportApi {
  listProjectReports(projectId: string): Promise<Report[]>;
  listRunReports(runId: string): Promise<Report[]>;
  generateReport(
    runId: string,
    title: string | null,
    mode: "formal" | "internal",
    customerCode: string | null
  ): Promise<Report>;
  getReport(reportId: string): Promise<Report>;
  createArchive(reportId: string): Promise<Archive>;
  getReportArchive(reportId: string): Promise<Archive>;
  getArchive(archiveId: string): Promise<Archive>;
  reportDownloadUrl(reportId: string): string;
  archiveDownloadUrl(archiveId: string): string;
}
