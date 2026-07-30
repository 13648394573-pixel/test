import { ChangeEvent, useEffect, useState } from "react";

import type {
  Evidence,
  EvidenceCategory,
  ExecutionResultValue,
  ResultDraftInput,
  RunResult,
  TestExecutionApi
} from "./types";


interface ResultEditorProps {
  api: TestExecutionApi;
  runId: string;
  runResult: RunResult;
  onChanged(result: RunResult): void;
}


export default function ResultEditor({
  api,
  runId,
  runResult,
  onChanged
}: ResultEditorProps) {
  const [draft, setDraft] = useState<ResultDraftInput>({
    result: runResult.result,
    actual_result: runResult.actual_result,
    blocked_reason: runResult.blocked_reason,
    test_notes: runResult.test_notes
  });
  const [evidences, setEvidences] = useState<Evidence[]>([]);
  const [category, setCategory] = useState<EvidenceCategory>("SCREENSHOT");
  const [description, setDescription] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState("");
  const locked = runResult.integrity_status === "LOCKED";

  useEffect(() => {
    api.listResultEvidence(runResult.id)
      .then(setEvidences)
      .catch((reason: Error) => setError(reason.message));
  }, [api, runResult.id]);

  useEffect(() => {
    setDraft({
      result: runResult.result,
      actual_result: runResult.actual_result,
      blocked_reason: runResult.blocked_reason,
      test_notes: runResult.test_notes
    });
  }, [runResult]);

  const save = async () => {
    try {
      setError("");
      onChanged(await api.updateResult(runId, runResult.id, draft));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "保存结果失败");
    }
  };

  const lock = async () => {
    if (!window.confirm("锁定后结果和附件不可修改，确认锁定？")) return;
    try {
      setError("");
      onChanged(await api.lockResult(runId, runResult.id));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "锁定结果失败");
    }
  };

  const upload = async () => {
    if (!file) return;
    try {
      const created = await api.uploadResultEvidence(
        runResult.id,
        category,
        file,
        description || null
      );
      setEvidences((current) => [...current, created]);
      setFile(null);
      setDescription("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "上传附件失败");
    }
  };

  const remove = async (evidenceId: string) => {
    try {
      await api.deleteEvidence(evidenceId);
      setEvidences((current) =>
        current.filter((item) => item.id !== evidenceId)
      );
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "删除附件失败");
    }
  };

  const chooseFile = (event: ChangeEvent<HTMLInputElement>) => {
    setFile(event.target.files?.[0] ?? null);
  };

  return (
    <div className="result-editor">
      <div className="result-integrity">
        <strong>{locked ? "已锁定" : "草稿"}</strong>
        {runResult.locked_at && <span>{runResult.locked_at}</span>}
      </div>
      <div className="result-fields">
        <label>
          测试结果
          <select
            aria-label={`测试结果 ${runResult.case_snapshot.case_code}`}
            disabled={locked}
            value={draft.result ?? ""}
            onChange={(event) =>
              setDraft((current) => ({
                ...current,
                result: (event.target.value || null) as
                  ExecutionResultValue | null
              }))
            }
          >
            <option value="">未选择</option>
            <option value="PASS">PASS</option>
            <option value="FAIL">FAIL</option>
            <option value="BLOCKED">BLOCKED</option>
          </select>
        </label>
        <label>
          实际结果
          <textarea
            disabled={locked}
            value={draft.actual_result ?? ""}
            onChange={(event) =>
              setDraft((current) => ({
                ...current,
                actual_result: event.target.value || null
              }))
            }
          />
        </label>
        <label>
          BLOCKED 原因
          <textarea
            disabled={locked}
            value={draft.blocked_reason ?? ""}
            onChange={(event) =>
              setDraft((current) => ({
                ...current,
                blocked_reason: event.target.value || null
              }))
            }
          />
        </label>
        <label>
          测试备注
          <textarea
            disabled={locked}
            value={draft.test_notes ?? ""}
            onChange={(event) =>
              setDraft((current) => ({
                ...current,
                test_notes: event.target.value || null
              }))
            }
          />
        </label>
      </div>
      {!locked && (
        <div className="result-actions">
          <button className="button button-quiet" type="button" onClick={save}>
            保存草稿
          </button>
          <button className="button button-primary" type="button" onClick={lock}>
            锁定结果
          </button>
        </div>
      )}

      <section className="evidence-panel" aria-label="结果附件">
        <h4>测试附件</h4>
        {evidences.length === 0 ? (
          <p>暂无附件</p>
        ) : (
          <ul>
            {evidences.map((evidence) => (
              <li key={evidence.id}>
                <a href={api.evidenceDownloadUrl(evidence.id)}>
                  {evidence.original_name}
                </a>
                <span>{evidence.category} · {evidence.file_size} B</span>
                {!locked && (
                  <button
                    className="button button-danger"
                    type="button"
                    aria-label={`删除附件 ${evidence.original_name}`}
                    onClick={() => remove(evidence.id)}
                  >
                    删除
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}
        {!locked && (
          <div className="evidence-upload">
            <select
              aria-label="附件类型"
              value={category}
              onChange={(event) =>
                setCategory(event.target.value as EvidenceCategory)
              }
            >
              <option value="SCREENSHOT">截图</option>
              <option value="LOG">日志</option>
              <option value="CONFIG">配置</option>
              <option value="OTHER">其他</option>
            </select>
            <input aria-label="选择附件" type="file" onChange={chooseFile} />
            <input
              aria-label="附件说明"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
            />
            <button
              className="button button-quiet"
              type="button"
              disabled={!file}
              onClick={upload}
            >
              上传附件
            </button>
          </div>
        )}
      </section>
      {error && <p className="error-message" role="alert">{error}</p>}
    </div>
  );
}
