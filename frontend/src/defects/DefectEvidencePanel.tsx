import { ChangeEvent, useEffect, useState } from "react";

import type { Evidence, EvidenceCategory } from "../testExecution/types";
import type { Defect, DefectApi } from "./types";


interface DefectEvidencePanelProps {
  defect: Defect;
  api: DefectApi;
}


export default function DefectEvidencePanel({
  defect,
  api
}: DefectEvidencePanelProps) {
  const [items, setItems] = useState<Evidence[]>([]);
  const [category, setCategory] = useState<EvidenceCategory>("SCREENSHOT");
  const [file, setFile] = useState<File | null>(null);
  const [description, setDescription] = useState("");
  const [error, setError] = useState("");
  const canAdd = defect.status !== "CLOSED";
  const canDelete = ["OPEN", "IN_PROGRESS", "REOPENED"].includes(
    defect.status
  );

  useEffect(() => {
    api.listEvidence(defect.id)
      .then(setItems)
      .catch((reason: Error) => setError(reason.message));
  }, [api, defect.id]);

  const chooseFile = (event: ChangeEvent<HTMLInputElement>) => {
    setFile(event.target.files?.[0] ?? null);
  };

  const upload = async () => {
    if (!file) return;
    try {
      const evidence = await api.uploadEvidence(
        defect.id,
        category,
        file,
        description || null
      );
      setItems((current) => [...current, evidence]);
      setFile(null);
      setDescription("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "上传附件失败");
    }
  };

  const remove = async (id: string) => {
    try {
      await api.deleteEvidence(id);
      setItems((current) => current.filter((item) => item.id !== id));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "删除附件失败");
    }
  };

  return (
    <section className="evidence-panel" aria-label="缺陷附件">
      <h3>缺陷附件</h3>
      {items.length === 0 ? (
        <p>暂无附件</p>
      ) : (
        <ul>
          {items.map((item) => (
            <li key={item.id}>
              <a href={api.evidenceDownloadUrl(item.id)}>
                {item.original_name}
              </a>
              <span>{item.category} · {item.file_size} B</span>
              {canDelete && (
                <button
                  className="button button-danger"
                  type="button"
                  aria-label={`删除附件 ${item.original_name}`}
                  onClick={() => remove(item.id)}
                >
                  删除
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
      {canAdd && (
        <div className="evidence-upload">
          <select
            aria-label="缺陷附件类型"
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
          <input aria-label="选择缺陷附件" type="file" onChange={chooseFile} />
          <input
            aria-label="缺陷附件说明"
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
      {defect.status === "RESOLVED" && (
        <small>已解决缺陷允许补充附件，但不能删除已有附件。</small>
      )}
      {defect.status === "CLOSED" && <small>已关闭缺陷附件只读。</small>}
      {error && <p className="error-message" role="alert">{error}</p>}
    </section>
  );
}
