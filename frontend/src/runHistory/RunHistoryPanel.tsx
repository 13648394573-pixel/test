import { FormEvent, useEffect, useState } from "react";

import { runHistoryApi } from "./api";
import type { RunComparison, RunHistoryApi, RunHistoryFilters, RunHistoryPage } from "./types";


interface Props {
  api?: RunHistoryApi;
  projectId?: string;
  revision?: number;
  onOpen(runId: string): void;
}


export default function RunHistoryPanel({ api = runHistoryApi, projectId, revision = 0, onOpen }: Props) {
  const [filters, setFilters] = useState<RunHistoryFilters>({ project_id: projectId, limit: 25, offset: 0 });
  const [page, setPage] = useState<RunHistoryPage>({ items: [], total: 0, limit: 25, offset: 0 });
  const [selected, setSelected] = useState<string[]>([]);
  const [comparison, setComparison] = useState<RunComparison | null>(null);
  const [error, setError] = useState("");

  const load = async (next = filters) => {
    try {
      setError("");
      const requestFilters = { ...next, project_id: projectId, limit: 25 };
      const loaded = await api.search(requestFilters);
      setFilters(requestFilters);
      setPage(loaded);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "加载运行历史失败");
    }
  };

  useEffect(() => { void load({ ...filters, project_id: projectId }); }, [projectId, revision]);

  const submit = (event: FormEvent) => { event.preventDefault(); void load({ ...filters, offset: 0 }); };
  const reset = () => void load({ project_id: projectId, limit: 25, offset: 0 });
  const movePage = (offset: number) => void load({ ...filters, offset });
  const toggle = (id: string) => setSelected((current) => current.includes(id) ? current.filter((item) => item !== id) : current.length < 5 ? [...current, id] : current);
  const compare = async () => {
    try { setComparison(await api.compare(selected)); setError(""); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "比较失败"); }
  };

  return (
    <section className="run-history" aria-labelledby="run-history-title">
      <h3 id="run-history-title">运行历史</h3>
      <form className="run-history-filters" onSubmit={submit}>
        <input aria-label="Run编号" placeholder="RUN-000001" value={filters.run_no ?? ""} onChange={(event) => setFilters({ ...filters, run_no: event.target.value })} />
        <input aria-label="项目版本" placeholder="项目版本" value={filters.project_version ?? ""} onChange={(event) => setFilters({ ...filters, project_version: event.target.value })} />
        <input aria-label="设备类型" placeholder="ONU/OLT/光猫" value={filters.device_type ?? ""} onChange={(event) => setFilters({ ...filters, device_type: event.target.value })} />
        <input aria-label="设备厂商" placeholder="设备厂商" value={filters.vendor ?? ""} onChange={(event) => setFilters({ ...filters, vendor: event.target.value })} />
        <input aria-label="设备型号" placeholder="设备型号" value={filters.model ?? ""} onChange={(event) => setFilters({ ...filters, model: event.target.value })} />
        <input aria-label="设备序列号" placeholder="DUT序列号" value={filters.serial_number ?? ""} onChange={(event) => setFilters({ ...filters, serial_number: event.target.value })} />
        <input aria-label="软件版本" placeholder="软件版本" value={filters.software_version ?? ""} onChange={(event) => setFilters({ ...filters, software_version: event.target.value })} />
        <input aria-label="开始时间起" type="datetime-local" value={filters.started_from ?? ""} onChange={(event) => setFilters({ ...filters, started_from: event.target.value })} />
        <input aria-label="开始时间止" type="datetime-local" value={filters.started_to ?? ""} onChange={(event) => setFilters({ ...filters, started_to: event.target.value })} />
        <select aria-label="Run状态" value={filters.status ?? ""} onChange={(event) => setFilters({ ...filters, status: event.target.value as RunHistoryFilters["status"] })}><option value="">全部状态</option><option value="IN_PROGRESS">执行中</option><option value="COMPLETED">已完成</option></select>
        <select aria-label="结果筛选" value={filters.result ?? ""} onChange={(event) => setFilters({ ...filters, result: event.target.value as RunHistoryFilters["result"] })}><option value="">全部结果</option><option value="PASS">PASS</option><option value="FAIL">FAIL</option><option value="BLOCKED">BLOCKED</option><option value="UNSET">未记录</option></select>
        <button className="button button-quiet" type="submit">筛选</button>
        <button className="button button-quiet" type="button" onClick={reset}>重置</button>
      </form>
      <div className="history-list">
        {page.items.map((run) => (
          <div className="history-item" key={run.id}>
            <input type="checkbox" aria-label={`选择 ${run.run_no}`} checked={selected.includes(run.id)} onChange={() => toggle(run.id)} />
            <button type="button" className="history-open" aria-label={`查看运行 ${run.id}`} onClick={() => onOpen(run.id)}><strong>{run.run_no}</strong><span>{run.device.serial_number ?? "—"}</span><span>{run.project_version}</span><span>{run.status === "COMPLETED" ? "已完成" : "执行中"}</span></button>
          </div>
        ))}
      </div>
      <div className="history-pagination">
        <span>共 {page.total} 条</span>
        <button className="button button-quiet" type="button" disabled={page.offset === 0} onClick={() => movePage(Math.max(0, page.offset - page.limit))}>上一页</button>
        <button className="button button-quiet" type="button" disabled={page.offset + page.items.length >= page.total} onClick={() => movePage(page.offset + page.limit)}>下一页</button>
      </div>
      <button className="button button-primary" type="button" disabled={selected.length < 2 || selected.length > 5} onClick={compare}>比较所选 Run</button>
      {comparison && <div className="run-comparison"><h4>Run结果比较</h4>{comparison.rows.map((row) => <div key={row.case_code} className="comparison-row"><strong>{row.case_code}</strong><span>{row.base.result ?? "—"}</span>{row.targets.map((target) => <span key={target.run_id}>{target.result ?? "—"} · {target.change}</span>)}</div>)}</div>}
      {error && <p className="error-message" role="alert">{error}</p>}
    </section>
  );
}
