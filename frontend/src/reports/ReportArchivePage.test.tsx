import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import type { TestExecutionApi, TestProject, TestRun } from "../testExecution/types";
import ReportArchivePage from "./ReportArchivePage";
import type { Archive, Report, ReportApi } from "./types";


const PROJECT: TestProject = {
  id: "project-1",
  name: "ONU Release",
  version: "R1",
  description: null,
  created_at: "2026-07-30T08:00:00",
  updated_at: "2026-07-30T08:00:00",
  case_selections: [{ case_source_id: "case-1" }]
};

const RUN: TestRun = {
  id: "run-1",
  project_id: "project-1",
  device_source_id: "device-1",
  device_snapshot: {
    device_type: "ONU",
    vendor: "Example",
    model: "X1",
    serial_number: "ONU-001",
    mac_address: null,
    hardware_version: "A1",
    software_version: "R1"
  },
  snapshot_version: 1,
  status: "COMPLETED",
  started_at: "2026-07-30T08:00:00",
  finished_at: "2026-07-30T09:00:00",
  environment_snapshot: null,
  results: []
};

const executionApi: Pick<TestExecutionApi, "listProjects" | "listRuns"> = {
  listProjects: async () => [PROJECT],
  listRuns: async () => [RUN]
};


class MemoryReportApi implements ReportApi {
  reports: Report[] = [];

  async listProjectReports() {
    return structuredClone(this.reports);
  }

  async listRunReports() {
    return structuredClone(this.reports);
  }

  async generateReport(runId: string, title: string | null) {
    const report: Report = {
      id: "report-1",
      report_no: "RPT-000001",
      project_id: "project-1",
      test_run_id: runId,
      report_version: 1,
      title: title ?? "Report",
      snapshot_version: 1,
      report_snapshot: {
        summary: { total: 3, pass: 2, fail: 1, blocked: 0, defects: 1 }
      },
      html_storage_path: "reports/report-1/report.html",
      html_sha256: "a".repeat(64),
      html_file_size: 100,
      generated_at: "2026-07-30T10:00:00",
      created_at: "2026-07-30T10:00:00",
      archive: null
    };
    this.reports = [report];
    return structuredClone(report);
  }

  async createArchive(reportId: string) {
    const archive: Archive = {
      id: "archive-1",
      archive_no: "ARC-000001",
      report_id: reportId,
      project_id: "project-1",
      manifest_version: 1,
      manifest_snapshot: {},
      archive_storage_path: "archives/archive-1.zip",
      archive_sha256: "b".repeat(64),
      archive_file_size: 200,
      archived_at: "2026-07-30T11:00:00",
      created_at: "2026-07-30T11:00:00"
    };
    this.reports[0].archive = archive;
    return structuredClone(archive);
  }

  async getReport() {
    return structuredClone(this.reports[0]);
  }

  async getReportArchive() {
    return structuredClone(this.reports[0].archive!);
  }

  async getArchive() {
    return structuredClone(this.reports[0].archive!);
  }

  reportDownloadUrl(id: string) {
    return `/api/reports/${id}/download`;
  }

  archiveDownloadUrl(id: string) {
    return `/api/archives/${id}/download`;
  }
}


afterEach(cleanup);


describe("ReportArchivePage", () => {
  it("generates a report, shows summary, and creates one archive", async () => {
    const api = new MemoryReportApi();
    render(<ReportArchivePage api={api} executionApi={executionApi} />);

    fireEvent.change(await screen.findByLabelText("Test Project"), {
      target: { value: PROJECT.id }
    });
    fireEvent.change(await screen.findByLabelText("Completed Run"), {
      target: { value: RUN.id }
    });
    fireEvent.change(screen.getByLabelText("Report Title"), {
      target: { value: "ONU Acceptance" }
    });
    fireEvent.click(screen.getByRole("button", { name: "Generate Report" }));

    expect(await screen.findByText("ONU Acceptance")).toBeInTheDocument();
    expect(screen.getByText(/TOTAL 3/)).toHaveTextContent("PASS 2");
    expect(screen.getByRole("link", { name: "Download HTML" }))
      .toHaveAttribute("href", "/api/reports/report-1/download");
    fireEvent.click(screen.getByRole("button", { name: "Create Archive" }));
    await waitFor(() =>
      expect(screen.getByRole("link", { name: "Download ZIP" }))
        .toHaveAttribute("href", "/api/archives/archive-1/download")
    );
    expect(
      screen.queryByRole("button", { name: "Create Archive" })
    ).not.toBeInTheDocument();
  });
});
