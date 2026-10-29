import { useEffect, useState } from "react";

import { testExecutionApi as defaultExecutionApi } from "../testExecution/api";
import type {
  TestExecutionApi,
  TestProject,
  TestRun
} from "../testExecution/types";
import { reportApi as defaultReportApi } from "./api";
import type { Report, ReportApi } from "./types";


interface Props {
  api?: ReportApi;
  executionApi?: Pick<TestExecutionApi, "listProjects" | "listRuns">;
}


export default function ReportArchivePage({
  api = defaultReportApi,
  executionApi = defaultExecutionApi
}: Props) {
  const [projects, setProjects] = useState<TestProject[]>([]);
  const [runs, setRuns] = useState<TestRun[]>([]);
  const [reports, setReports] = useState<Report[]>([]);
  const [projectId, setProjectId] = useState("");
  const [runId, setRunId] = useState("");
  const [title, setTitle] = useState("");
  const [mode, setMode] = useState<"formal" | "internal">("formal");
  const [error, setError] = useState("");

  useEffect(() => {
    executionApi.listProjects()
      .then(setProjects)
      .catch((reason: Error) => setError(reason.message));
  }, [executionApi]);

  const selectProject = async (selectedProjectId: string) => {
    setProjectId(selectedProjectId);
    setRunId("");
    setError("");
    if (!selectedProjectId) {
      setRuns([]);
      setReports([]);
      return;
    }
    try {
      const [runItems, reportItems] = await Promise.all([
        executionApi.listRuns(selectedProjectId),
        api.listProjectReports(selectedProjectId)
      ]);
      setRuns(runItems.filter((run) => run.status === "COMPLETED"));
      setReports(reportItems);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to load reports");
    }
  };

  const generate = async () => {
    if (!runId) return;
    try {
      const report = await api.generateReport(runId, title.trim() || null, mode);
      setReports((current) => [report, ...current]);
      setTitle("");
      setError("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to generate report");
    }
  };

  const createArchive = async (report: Report) => {
    try {
      const archive = await api.createArchive(report.id);
      setReports((current) =>
        current.map((item) =>
          item.id === report.id ? { ...item, archive } : item
        )
      );
      setError("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to create archive");
    }
  };

  return (
    <section aria-labelledby="report-archive-title">
      <div className="page-heading">
        <div>
          <p className="section-kicker">Report & Archive</p>
          <h2 id="report-archive-title">Report & Archive</h2>
          <p>Generate immutable HTML reports and integrity-checked archives.</p>
        </div>
      </div>
      {error && <p className="error-message" role="alert">{error}</p>}
      <div className="execution-project-form">
        <div className="form-grid">
          <label>
            Test Project
            <select
              value={projectId}
              onChange={(event) => { void selectProject(event.target.value); }}
            >
              <option value="">Select project</option>
              {projects.map((project) => (
                <option key={project.id} value={project.id}>
                  {project.name} · {project.version}
                </option>
              ))}
            </select>
          </label>
          <label>
            Completed Run
            <select
              value={runId}
              onChange={(event) => setRunId(event.target.value)}
              disabled={!projectId}
            >
              <option value="">Select completed run</option>
              {runs.map((run) => (
                <option key={run.id} value={run.id}>
                  {run.device_snapshot.serial_number} · {run.finished_at}
                </option>
              ))}
            </select>
          </label>
          <label>
            Report Title
            <input
              value={title}
              onChange={(event) => setTitle(event.target.value)}
            />
          </label>
          <label>
            Report Mode
            <select
              value={mode}
              onChange={(event) =>
                setMode(event.target.value as "formal" | "internal")
              }
            >
              <option value="formal">Formal（客户验收）</option>
              <option value="internal">Internal（内部存档）</option>
            </select>
          </label>
          <button
            className="button button-primary"
            type="button"
            disabled={!runId}
            onClick={generate}
          >
            Generate Report
          </button>
        </div>
      </div>
      <div className="history-list">
        {reports.length === 0 ? (
          <p className="empty-state">No generated reports.</p>
        ) : reports.map((report) => {
          const summary = report.report_snapshot.summary;
          return (
            <article className="result-card" key={report.id}>
              <header>
                <div>
                  <span className="mono">{report.report_no}</span>
                  <h3>{report.title}</h3>
                </div>
                <strong>Version {report.report_version}</strong>
              </header>
              <p>
                TOTAL {summary.total} · PASS {summary.pass} · FAIL {summary.fail}
                {" · "}BLOCKED {summary.blocked} · DEFECTS {summary.defects}
              </p>
              <div className="row-actions">
                <a
                  className="button button-quiet"
                  href={api.reportDownloadUrl(report.id)}
                >
                  Download HTML
                </a>
                {report.archive ? (
                  <a
                    className="button button-primary"
                    href={api.archiveDownloadUrl(report.archive.id)}
                  >
                    Download ZIP
                  </a>
                ) : (
                  <button
                    className="button button-primary"
                    type="button"
                    onClick={() => createArchive(report)}
                  >
                    Create Archive
                  </button>
                )}
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}
