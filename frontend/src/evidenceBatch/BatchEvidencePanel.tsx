import { ChangeEvent, useEffect, useState } from "react";

import type { Evidence, EvidenceCategory, RunResult } from "../testExecution/types";


interface Props {
  results: RunResult[];
  upload(resultIds: string[], files: File[], category: EvidenceCategory, description: string | null): Promise<Evidence[]>;
  onUploaded(): void;
}


export default function BatchEvidencePanel({ results, upload, onUploaded }: Props) {
  const [selected, setSelected] = useState<string[]>([]);
  const [files, setFiles] = useState<File[]>([]);
  const [category, setCategory] = useState<EvidenceCategory>("SCREENSHOT");
  const [description, setDescription] = useState("");
  const [error, setError] = useState("");
  const resultSetKey = results.map((item) => item.id).join("|");
  useEffect(() => {
    setSelected([]);
    setFiles([]);
    setDescription("");
    setError("");
  }, [resultSetKey]);
  const toggle = (id: string) => setSelected((current) => current.includes(id) ? current.filter((item) => item !== id) : [...current, id]);
  const choose = (event: ChangeEvent<HTMLInputElement>) => setFiles(Array.from(event.target.files ?? []));
  const submit = async () => {
    try {
      await upload(selected, files, category, description || null);
      setSelected([]); setFiles([]); setDescription(""); setError(""); onUploaded();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "批量上传失败"); }
  };
  return <section className="batch-evidence" aria-label="批量测试附件">
    <h4>批量关联附件</h4>
    <div className="batch-result-selector">{results.map((result) => <label key={result.id}><input type="checkbox" aria-label={`关联 ${result.case_snapshot.case_code}`} disabled={result.integrity_status === "LOCKED"} checked={selected.includes(result.id)} onChange={() => toggle(result.id)} />{result.case_snapshot.case_code}{result.integrity_status === "LOCKED" ? "（已锁定）" : ""}</label>)}</div>
    <select aria-label="批量附件类型" value={category} onChange={(event) => setCategory(event.target.value as EvidenceCategory)}><option value="SCREENSHOT">截图</option><option value="LOG">日志</option><option value="CONFIG">配置</option><option value="OTHER">其他</option></select>
    <input aria-label="批量附件文件" type="file" multiple onChange={choose} />
    <input aria-label="批量附件说明" value={description} onChange={(event) => setDescription(event.target.value)} />
    <button className="button button-quiet" type="button" disabled={!selected.length || !files.length} onClick={submit}>批量上传</button>
    <span>{selected.length} 个结果 · {files.length} 个文件</span>
    {error && <p className="error-message" role="alert">{error}</p>}
  </section>;
}
