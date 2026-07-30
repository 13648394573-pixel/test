import { FormEvent, useEffect, useMemo, useState } from "react";

import { testExecutionApi } from "../testExecution/api";
import type {
  RunResult,
  TestExecutionApi
} from "../testExecution/types";
import { defectApi } from "./api";
import DefectEvidencePanel from "./DefectEvidencePanel";
import type {
  Defect,
  DefectApi,
  DefectInput,
  DefectUpdate,
  Severity
} from "./types";


interface DefectPageProps {
  api?: DefectApi;
  executionApi?: TestExecutionApi;
}

const EMPTY_FORM: DefectInput = {
  source_run_result_id: "",
  title: "",
  description: "",
  reproduction_steps: "",
  severity: "S2"
};


export default function DefectPage({
  api = defectApi,
  executionApi = testExecutionApi
}: DefectPageProps) {
  const [defects, setDefects] = useState<Defect[]>([]);
  const [evidence, setEvidence] = useState<RunResult[]>([]);
  const [active, setActive] = useState<Defect | null>(null);
  const [form, setForm] = useState<DefectInput>(EMPTY_FORM);
  const [editing, setEditing] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [resolutionNotes, setResolutionNotes] = useState("");
  const [regressionResultId, setRegressionResultId] = useState("");
  const [regressionNotes, setRegressionNotes] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [severityFilter, setSeverityFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([api.list(), executionApi.listProjects()])
      .then(async ([items, projects]) => {
        const histories = await Promise.all(
          projects.map((project) => executionApi.listRuns(project.id))
        );
        setDefects(items);
        setEvidence(histories.flatMap((runs) => runs.flatMap((run) => run.results)));
      })
      .catch((reason: Error) => setError(reason.message))
      .finally(() => setLoading(false));
  }, [api, executionApi]);

  const eligibleSources = useMemo(() => {
    const used = new Set(defects.map((defect) => defect.source_run_result_id));
    return evidence.filter(
      (result) =>
        result.integrity_status === "LOCKED" &&
        (result.result === "FAIL" || result.result === "BLOCKED") &&
        !used.has(result.id)
    );
  }, [defects, evidence]);

  const visibleDefects = defects.filter(
    (defect) =>
      (!statusFilter || defect.status === statusFilter) &&
      (!severityFilter || defect.severity === severityFilter)
  );

  const regressionCandidates = active
    ? evidence.filter(
        (result) =>
          result.integrity_status === "LOCKED" &&
          result.result !== null &&
          result.id !== active.source_run_result_id &&
          result.case_source_id === active.source_run_result.case_source_id &&
          !active.regressions.some(
            (regression) => regression.verification_run_result_id === result.id
          )
      )
    : [];

  const replaceDefect = (saved: Defect) => {
    setDefects((current) => {
      const exists = current.some((item) => item.id === saved.id);
      return exists
        ? current.map((item) => item.id === saved.id ? saved : item)
        : [saved, ...current];
    });
    setActive(saved);
  };

  const startCreate = () => {
    setEditing(false);
    setForm(EMPTY_FORM);
    setShowForm(true);
    setError("");
  };

  const startEdit = () => {
    if (!active) return;
    setEditing(true);
    setForm({
      source_run_result_id: active.source_run_result_id,
      title: active.title,
      description: active.description,
      reproduction_steps: active.reproduction_steps,
      severity: active.severity
    });
    setShowForm(true);
  };

  const save = async (event: FormEvent) => {
    event.preventDefault();
    try {
      const saved = editing && active
        ? await api.update(active.id, toUpdate(form))
        : await api.create(form);
      replaceDefect(saved);
      setShowForm(false);
      setEditing(false);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "保存缺陷失败");
    }
  };

  const openDefect = async (id: string) => {
    try {
      setActive(await api.get(id));
      setShowForm(false);
      setError("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "加载缺陷失败");
    }
  };

  const transition = async (
    targetStatus: "IN_PROGRESS" | "RESOLVED"
  ) => {
    if (!active) return;
    try {
      const saved = await api.transition(
        active.id,
        targetStatus,
        targetStatus === "RESOLVED" ? resolutionNotes : null
      );
      replaceDefect(saved);
      setResolutionNotes("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "状态流转失败");
    }
  };

  const recordRegression = async () => {
    if (!active || !regressionResultId) return;
    try {
      await api.createRegression(active.id, {
        verification_run_result_id: regressionResultId,
        notes: regressionNotes || null
      });
      const refreshed = await api.get(active.id);
      replaceDefect(refreshed);
      setRegressionResultId("");
      setRegressionNotes("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "记录回归失败");
    }
  };

  return (
    <section className="defect-page" aria-labelledby="defect-title">
      <div className="page-heading">
        <div>
          <p className="section-kicker">Defect & Regression</p>
          <h2 id="defect-title">缺陷闭环</h2>
          <p>从失败证据创建缺陷，记录处理状态和追加式回归结果。</p>
        </div>
        <button
          className="button button-primary"
          type="button"
          onClick={startCreate}
        >
          新建缺陷
        </button>
      </div>

      {error && <p className="error-message" role="alert">{error}</p>}

      {showForm && (
        <form className="defect-form" onSubmit={save}>
          <div className="form-heading">
            <h3>{editing ? "编辑缺陷" : "新建缺陷"}</h3>
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
              失败证据
              <select
                required
                disabled={editing}
                value={form.source_run_result_id}
                onChange={(event) => setForm({
                  ...form,
                  source_run_result_id: event.target.value
                })}
              >
                <option value="">请选择失败或阻塞结果</option>
                {(editing && active
                  ? [active.source_run_result]
                  : eligibleSources
                ).map((result) => (
                  <option key={result.id} value={result.id}>
                    {result.case_snapshot.case_code} · {result.result}
                  </option>
                ))}
              </select>
            </label>
            <label>
              严重程度
              <select
                value={form.severity}
                onChange={(event) => setForm({
                  ...form,
                  severity: event.target.value as Severity
                })}
              >
                {(["S1", "S2", "S3", "S4"] as const).map((value) => (
                  <option key={value}>{value}</option>
                ))}
              </select>
            </label>
            <label className="wide-field">
              标题
              <input
                required
                value={form.title}
                onChange={(event) => setForm({
                  ...form,
                  title: event.target.value
                })}
              />
            </label>
            <label className="wide-field">
              现象说明
              <textarea
                required
                value={form.description}
                onChange={(event) => setForm({
                  ...form,
                  description: event.target.value
                })}
              />
            </label>
            <label className="wide-field">
              复现步骤
              <textarea
                required
                value={form.reproduction_steps}
                onChange={(event) => setForm({
                  ...form,
                  reproduction_steps: event.target.value
                })}
              />
            </label>
          </div>
          <div className="form-actions">
            <button className="button button-primary" type="submit">
              保存缺陷
            </button>
          </div>
        </form>
      )}

      <div className="defect-filters">
        <label>
          状态
          <select
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value)}
          >
            <option value="">全部</option>
            {["OPEN", "IN_PROGRESS", "RESOLVED", "REOPENED", "CLOSED"].map(
              (value) => <option key={value}>{value}</option>
            )}
          </select>
        </label>
        <label>
          严重程度
          <select
            value={severityFilter}
            onChange={(event) => setSeverityFilter(event.target.value)}
          >
            <option value="">全部</option>
            {["S1", "S2", "S3", "S4"].map(
              (value) => <option key={value}>{value}</option>
            )}
          </select>
        </label>
      </div>

      <div className="defect-layout">
        <div className="table-panel">
          {loading ? (
            <p className="empty-state">正在加载缺陷…</p>
          ) : visibleDefects.length === 0 ? (
            <p className="empty-state">暂无缺陷</p>
          ) : (
            <div className="defect-list">
              {visibleDefects.map((defect) => (
                <button
                  key={defect.id}
                  type="button"
                  className="defect-list-item"
                  aria-label={`打开 ${defect.defect_code}`}
                  onClick={() => openDefect(defect.id)}
                >
                  <span className="mono">{defect.defect_code}</span>
                  <strong>{defect.title}</strong>
                  <span>{defect.severity}</span>
                  <span>{defect.status}</span>
                </button>
              ))}
            </div>
          )}
        </div>

        {active && (
          <article className="defect-detail">
            <header>
              <div>
                <span className="mono">{active.defect_code}</span>
                <h3>{active.title}</h3>
              </div>
              <strong className="run-status">{active.status}</strong>
            </header>
            <p>{active.description}</p>
            <dl>
              <div><dt>严重程度</dt><dd>{active.severity}</dd></div>
              <div>
                <dt>源用例</dt>
                <dd>{active.source_run_result.case_snapshot.case_code}</dd>
              </div>
              <div>
                <dt>源结果</dt>
                <dd>{active.source_run_result.result}</dd>
              </div>
            </dl>
            <section>
              <h3>复现步骤</h3>
              <p>{active.reproduction_steps}</p>
            </section>

            <div className="defect-actions">
              {active.status !== "CLOSED" && (
                <button
                  className="button button-quiet"
                  type="button"
                  onClick={startEdit}
                >
                  编辑缺陷
                </button>
              )}
              {(active.status === "OPEN" || active.status === "REOPENED") && (
                <button
                  className="button button-primary"
                  type="button"
                  onClick={() => transition("IN_PROGRESS")}
                >
                  开始处理
                </button>
              )}
            </div>

            {active.status === "IN_PROGRESS" && (
              <div className="resolution-panel">
                <label>
                  解决说明
                  <textarea
                    value={resolutionNotes}
                    onChange={(event) => setResolutionNotes(event.target.value)}
                  />
                </label>
                <button
                  className="button button-primary"
                  type="button"
                  disabled={!resolutionNotes.trim()}
                  onClick={() => transition("RESOLVED")}
                >
                  标记已解决
                </button>
              </div>
            )}

            {active.status === "RESOLVED" && (
              <div className="regression-panel">
                <h3>新增回归记录</h3>
                <label>
                  回归证据
                  <select
                    value={regressionResultId}
                    onChange={(event) =>
                      setRegressionResultId(event.target.value)
                    }
                  >
                    <option value="">请选择同用例执行结果</option>
                    {regressionCandidates.map((result) => (
                      <option key={result.id} value={result.id}>
                        {result.case_snapshot.case_code} · {result.result}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  回归说明
                  <textarea
                    value={regressionNotes}
                    onChange={(event) => setRegressionNotes(event.target.value)}
                  />
                </label>
                <button
                  className="button button-primary"
                  type="button"
                  disabled={!regressionResultId}
                  onClick={recordRegression}
                >
                  记录回归
                </button>
              </div>
            )}

            <DefectEvidencePanel defect={active} api={api} />

            <section className="regression-history">
              <h3>回归历史</h3>
              {active.regressions.length === 0 ? (
                <p>暂无回归记录</p>
              ) : (
                <ol>
                  {active.regressions.map((regression) => (
                    <li key={regression.id}>
                      <strong>{regression.result}</strong>
                      <span>{regression.notes ?? "无说明"}</span>
                    </li>
                  ))}
                </ol>
              )}
            </section>
          </article>
        )}
      </div>
    </section>
  );
}


function toUpdate(input: DefectInput): DefectUpdate {
  return {
    title: input.title,
    description: input.description,
    reproduction_steps: input.reproduction_steps,
    severity: input.severity
  };
}
