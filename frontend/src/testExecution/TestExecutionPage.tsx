import { FormEvent, useEffect, useState } from "react";

import { deviceApi as defaultDeviceApi } from "../devices/api";
import type { Device, DeviceApi } from "../devices/types";
import { environmentApi as defaultEnvironmentApi } from "../environments/api";
import EnvironmentSnapshotPanel from "../environments/EnvironmentSnapshotPanel";
import BatchEvidencePanel from "../evidenceBatch/BatchEvidencePanel";
import RunHistoryPanel from "../runHistory/RunHistoryPanel";
import { runHistoryApi as defaultRunHistoryApi } from "../runHistory/api";
import type { RunHistoryApi } from "../runHistory/types";
import type {
  EnvironmentApi,
  EnvironmentProfile
} from "../environments/types";
import { testCaseApi as defaultTestCaseApi } from "../testCases/api";
import type { TestCase, TestCaseApi } from "../testCases/types";
import { testExecutionApi } from "./api";
import ResultEditor from "./ResultEditor";
import type {
  TestExecutionApi,
  TestProject,
  TestProjectInput,
  TestRun
} from "./types";


interface TestExecutionPageProps {
  api?: TestExecutionApi;
  deviceApi?: DeviceApi;
  testCaseApi?: TestCaseApi;
  environmentApi?: EnvironmentApi;
  runHistoryApi?: RunHistoryApi;
}

const EMPTY_PROJECT: TestProjectInput = {
  name: "",
  version: "",
  description: null,
  case_source_ids: []
};


export default function TestExecutionPage({
  api = testExecutionApi,
  deviceApi = defaultDeviceApi,
  testCaseApi = defaultTestCaseApi,
  environmentApi = defaultEnvironmentApi,
  runHistoryApi
}: TestExecutionPageProps) {
  const [projects, setProjects] = useState<TestProject[]>([]);
  const [devices, setDevices] = useState<Device[]>([]);
  const [testCases, setTestCases] = useState<TestCase[]>([]);
  const [environments, setEnvironments] = useState<EnvironmentProfile[]>([]);
  const [activeProject, setActiveProject] = useState<TestProject | null>(null);
  const [activeRun, setActiveRun] = useState<TestRun | null>(null);
  const [runs, setRuns] = useState<TestRun[]>([]);
  const [editing, setEditing] = useState<TestProject | null>(null);
  const [form, setForm] = useState<TestProjectInput>(EMPTY_PROJECT);
  const [showForm, setShowForm] = useState(false);
  const [selectedDeviceId, setSelectedDeviceId] = useState("");
  const [selectedEnvironmentId, setSelectedEnvironmentId] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [evidenceRevision, setEvidenceRevision] = useState(0);
  const effectiveRunHistoryApi: RunHistoryApi = runHistoryApi ?? (
    api === testExecutionApi
      ? defaultRunHistoryApi
      : {
          search: async (filters) => {
            const projectId = filters.project_id ?? activeProject?.id ?? "";
            const items = (await api.listRuns(projectId)).map((run) => ({
              id: run.id,
              run_no: run.run_no ?? run.id,
              project_id: run.project_id,
              project_name: activeProject?.name ?? "",
              project_version: activeProject?.version ?? "",
              device: {
                device_type: run.device_snapshot.device_type,
                vendor: run.device_snapshot.vendor,
                model: run.device_snapshot.model,
                serial_number: run.device_snapshot.serial_number,
                software_version: run.device_snapshot.software_version
              },
              status: run.status,
              summary: {
                total: run.results.length,
                pass: run.results.filter((item) => item.result === "PASS").length,
                fail: run.results.filter((item) => item.result === "FAIL").length,
                blocked: run.results.filter((item) => item.result === "BLOCKED").length,
                unset: run.results.filter((item) => item.result === null).length
              },
              started_at: run.started_at,
              finished_at: run.finished_at
            }));
            return { items, total: items.length, limit: 25, offset: 0 };
          },
          compare: defaultRunHistoryApi.compare
        }
  );

  useEffect(() => {
    Promise.all([
      api.listProjects(),
      deviceApi.list(),
      testCaseApi.list(),
      environmentApi.list()
    ])
      .then(([projectItems, deviceItems, caseItems, environmentItems]) => {
        setProjects(projectItems);
        setDevices(deviceItems);
        setTestCases(caseItems.filter((testCase) => testCase.enabled));
        setEnvironments(environmentItems.filter((profile) => profile.enabled));
      })
      .catch((reason: Error) => setError(reason.message))
      .finally(() => setLoading(false));
  }, [api, deviceApi, testCaseApi, environmentApi]);

  const startCreate = () => {
    setEditing(null);
    setForm(EMPTY_PROJECT);
    setShowForm(true);
    setError("");
  };

  const startEdit = (project: TestProject) => {
    setEditing(project);
    setForm({
      name: project.name,
      version: project.version,
      description: project.description,
      case_source_ids: project.case_selections.map(
        (selection) => selection.case_source_id
      )
    });
    setShowForm(true);
    setError("");
  };

  const saveProject = async (event: FormEvent) => {
    event.preventDefault();
    try {
      const saved = editing
        ? await api.updateProject(editing.id, form)
        : await api.createProject(form);
      setProjects((current) =>
        editing
          ? current.map((project) => project.id === saved.id ? saved : project)
          : [saved, ...current]
      );
      if (activeProject?.id === saved.id) {
        setActiveProject(saved);
      }
      setShowForm(false);
      setEditing(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "保存测试项目失败");
    }
  };

  const deleteProject = async (project: TestProject) => {
    if (!window.confirm(`确认删除测试项目 ${project.name}？`)) {
      return;
    }
    try {
      await api.deleteProject(project.id);
      setProjects((current) =>
        current.filter((candidate) => candidate.id !== project.id)
      );
      if (activeProject?.id === project.id) {
        setActiveProject(null);
        setActiveRun(null);
        setRuns([]);
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "删除测试项目失败");
    }
  };

  const openProject = async (project: TestProject) => {
    setActiveProject(project);
    setActiveRun(null);
    setError("");
    try {
      setRuns(await api.listRuns(project.id));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "加载运行历史失败");
    }
  };

  const createRun = async () => {
    if (!activeProject || !selectedDeviceId || !selectedEnvironmentId) {
      return;
    }
    try {
      const run = await api.createRun(
        activeProject.id,
        selectedDeviceId,
        selectedEnvironmentId
      );
      setRuns((current) => [run, ...current]);
      setActiveRun(run);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "创建执行失败");
    }
  };

  const openRun = async (runId: string) => {
    try {
      setActiveRun(await api.getRun(runId));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "加载运行详情失败");
    }
  };

  const toggleCase = (caseId: string) => {
    setForm((current) => ({
      ...current,
      case_source_ids: current.case_source_ids.includes(caseId)
        ? current.case_source_ids.filter((id) => id !== caseId)
        : [...current.case_source_ids, caseId]
    }));
  };

  return (
    <section className="test-execution" aria-labelledby="test-execution-title">
      <div className="page-heading">
        <div>
          <p className="section-kicker">Test Execution</p>
          <h2 id="test-execution-title">测试执行</h2>
          <p>创建测试项目，选择设备并记录每条用例的手工执行结果。</p>
        </div>
        <button className="button button-primary" type="button" onClick={startCreate}>
          新建测试项目
        </button>
      </div>

      {error && <p className="error-message" role="alert">{error}</p>}

      {showForm && (
        <form className="execution-project-form" onSubmit={saveProject}>
          <div className="form-heading">
            <h3>{editing ? "编辑测试项目" : "新建测试项目"}</h3>
            <button
              className="button button-quiet"
              type="button"
              onClick={() => setShowForm(false)}
            >
              取消
            </button>
          </div>
          <div className="form-grid">
            <label>
              项目名称
              <input
                required
                value={form.name}
                onChange={(event) =>
                  setForm((current) => ({ ...current, name: event.target.value }))
                }
              />
            </label>
            <label>
              版本
              <input
                required
                value={form.version}
                onChange={(event) =>
                  setForm((current) => ({ ...current, version: event.target.value }))
                }
              />
            </label>
            <label className="wide-field">
              说明
              <textarea
                value={form.description ?? ""}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    description: event.target.value || null
                  }))
                }
              />
            </label>
          </div>
          <fieldset className="case-selector">
            <legend>选择测试用例</legend>
            {testCases.map((testCase) => (
              <label key={testCase.id}>
                <input
                  type="checkbox"
                  checked={form.case_source_ids.includes(testCase.id)}
                  onChange={() => toggleCase(testCase.id)}
                />
                <span className="mono">{testCase.case_code}</span>
                <span>{testCase.title}</span>
              </label>
            ))}
          </fieldset>
          <div className="form-actions">
            <button
              className="button button-primary"
              type="submit"
              disabled={form.case_source_ids.length === 0}
            >
              保存项目
            </button>
          </div>
        </form>
      )}

      <div className="table-panel">
        {loading ? (
          <p className="empty-state">正在加载测试项目…</p>
        ) : projects.length === 0 ? (
          <p className="empty-state">暂无测试项目</p>
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>项目名称</th>
                  <th>版本</th>
                  <th>用例数</th>
                  <th>说明</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {projects.map((project) => (
                  <tr key={project.id}>
                    <td>{project.name}</td>
                    <td>{project.version}</td>
                    <td>{project.case_selections.length}</td>
                    <td>{project.description ?? "—"}</td>
                    <td>
                      <div className="row-actions">
                        <button
                          className="button button-primary"
                          type="button"
                          aria-label={`打开 ${project.name}`}
                          onClick={() => openProject(project)}
                        >
                          打开
                        </button>
                        <button
                          className="button button-quiet"
                          type="button"
                          aria-label={`编辑 ${project.name}`}
                          onClick={() => startEdit(project)}
                        >
                          编辑
                        </button>
                        <button
                          className="button button-danger"
                          type="button"
                          aria-label={`删除 ${project.name}`}
                          onClick={() => deleteProject(project)}
                        >
                          删除
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {activeProject && (
        <div className="execution-workspace">
          <div className="run-launcher">
            <div>
              <p className="section-kicker">Active Project</p>
              <h3>{activeProject.name} · {activeProject.version}</h3>
            </div>
            <label>
              执行设备
              <select
                value={selectedDeviceId}
                onChange={(event) => setSelectedDeviceId(event.target.value)}
              >
                <option value="">请选择设备</option>
                {devices.map((device) => (
                  <option key={device.id} value={device.id}>
                    {device.vendor} {device.model} · {device.serial_number}
                  </option>
                ))}
              </select>
            </label>
            <label>
              环境模板
              <select
                value={selectedEnvironmentId}
                onChange={(event) => setSelectedEnvironmentId(event.target.value)}
              >
                <option value="">请选择启用的环境模板</option>
                {environments.map((profile) => (
                  <option key={profile.id} value={profile.id}>
                    {profile.name}
                  </option>
                ))}
              </select>
            </label>
            <button
              className="button button-primary"
              type="button"
              disabled={!selectedDeviceId || !selectedEnvironmentId}
              onClick={createRun}
            >
              创建执行
            </button>
          </div>

          <RunHistoryPanel
            api={effectiveRunHistoryApi}
            projectId={activeProject.id}
            revision={runs.length}
            onOpen={openRun}
          />

          {activeRun && (
            <section className="run-detail" aria-labelledby="run-detail-title">
              <div className="run-detail-heading">
                <div>
                  <p className="section-kicker">Run Detail</p>
                  <h3 id="run-detail-title">{activeRun.device_snapshot.serial_number}</h3>
                  <p>
                    {activeRun.device_snapshot.vendor} {activeRun.device_snapshot.model}
                    {" · "}快照版本 {activeRun.snapshot_version}
                  </p>
                </div>
                <span className="run-status">
                  {activeRun.status === "COMPLETED" ? "已完成" : "执行中"}
                </span>
              </div>

              <EnvironmentSnapshotPanel snapshot={activeRun.environment_snapshot} />

              <BatchEvidencePanel
                results={activeRun.results}
                upload={api.uploadBatchEvidence ?? (async () => {
                  throw new Error("批量附件接口不可用");
                })}
                onUploaded={() => setEvidenceRevision((value) => value + 1)}
              />

              <div className="result-list">
                {activeRun.results.map((runResult) => (
                  <article className="result-card" key={runResult.id}>
                    <header>
                      <div>
                        <span className="mono">{runResult.case_snapshot.case_code}</span>
                        <h3>{runResult.case_snapshot.title}</h3>
                      </div>
                      <div>
                        <span>快照版本 {runResult.snapshot_version}</span>
                        <strong>结果：{runResult.result ?? "未执行"}</strong>
                      </div>
                    </header>
                    <ol>
                      {runResult.case_snapshot.steps.map((step) => (
                        <li key={step.step_number}>
                          <p>{step.action}</p>
                          <small>预期：{step.expected_result}</small>
                        </li>
                      ))}
                    </ol>
                    <ResultEditor
                      api={api}
                      runId={activeRun.id}
                      runResult={runResult}
                      evidenceRevision={evidenceRevision}
                      onChanged={() => { void openRun(activeRun.id); }}
                    />
                  </article>
                ))}
              </div>
            </section>
          )}
        </div>
      )}
    </section>
  );
}
