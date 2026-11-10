import { FormEvent, useRef, useState } from "react";

interface PortOperation {
  operation_id: string; session_id: string; kind: "CREATE" | "DELETE"; port_id: number;
  serial_number: string; line_profile_id: number; service_profile_id: number;
  consumers: string[]; baseline_hash: string; read_hash: string; creation_event_id: string | null;
  mapping: { olt_binding_hash: string; fsp: string; ont_id: number; vlan: number; gemport: number;
    user_vlan: number; candidate_id: number | null; tag_transform: string; business_type: string };
}
interface Interaction {
  id: string; instructions: string; options: string[]; preview_hash: string; action_code: string | null;
  target: Record<string, string | number>; affected_service_ports: number[];
  service_port_preview?: { operations: PortOperation[]; evidence_ids: string[]; retained_consumers: string[] } | null;
}
interface ExecutionView {
  session_id: string; test_run_id: string; run_result_id: string; status: string;
  integrity_status: "DRAFT" | "LOCKED"; runner_configured: boolean;
  pending_interaction: Interaction | null;
  cleanup_available?: boolean;
  cleanup_preview?: { operations: PortOperation[]; evidence_ids: string[]; retained_consumers: string[]; preview_hash: string } | null;
  cleanup_outcome?: { status: string; items: { port_id: number; status: string }[] } | null;
}

function PortOperations({ operations }: { operations: PortOperation[] }) {
  return <>{operations.map((op) => <div key={op.operation_id}><dl>
    {Object.entries({ "操作": op.kind, "端口 ID": op.port_id, "SN": op.serial_number,
      "FSP": op.mapping.fsp, "ONT ID": op.mapping.ont_id, "Line Profile": op.line_profile_id,
      "Service Profile": op.service_profile_id, "业务 VLAN": op.mapping.vlan,
      "GEM": op.mapping.gemport, "用户 VLAN": op.mapping.user_vlan,
      "转换方式": op.mapping.tag_transform, "业务类型": op.mapping.business_type,
      "候选 ID": op.mapping.candidate_id ?? "无", "消费者": op.consumers.join(" / "),
      "创建事件": op.creation_event_id ?? "尚未创建", "操作 ID": op.operation_id,
      "OLT 绑定 hash": op.mapping.olt_binding_hash, "基线 hash": op.baseline_hash,
      "读取 hash": op.read_hash }).map(([label, value]) => <div key={label}><dt>{label}</dt><dd className="mono">{value}</dd></div>)}
  </dl></div>)}</>;
}

async function request(path: string, body?: object): Promise<ExecutionView> {
  const response = await fetch(path, body === undefined ? { cache: "no-store" } : {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body)
  });
  if (!response.ok) throw new Error(`执行会话请求失败（${response.status}），请重新读取并核对。`);
  return response.json();
}

export default function LocalExecutionApproval() {
  const [sessionId, setSessionId] = useState("");
  const [view, setView] = useState<ExecutionView | null>(null);
  const [checked, setChecked] = useState(false);
  const [cleanupChecked, setCleanupChecked] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const inFlight = useRef(false);
  const pending = view?.pending_interaction;
  const missingPortPreview = !!pending && ["create_service_port", "delete_service_port", "cleanup_service_ports"]
    .includes(pending.action_code ?? "") && !pending.service_port_preview;
  const editable = view?.integrity_status === "DRAFT" && view.runner_configured;
  const available = editable && view?.status === "WAITING_OPERATOR" && !missingPortPreview;
  const cleanupAvailable = editable && view?.cleanup_available && ["WAITING_OPERATOR", "RECOVERY_REQUIRED"].includes(view.status);

  async function perform(path: string, body?: object) {
    if (inFlight.current) return;
    inFlight.current = true;
    setBusy(true); setChecked(false); setCleanupChecked(false); setError(""); setView(null);
    try { setView(await request(path, body)); }
    catch (e) { setError(e instanceof Error ? e.message : "读取失败"); }
    finally { inFlight.current = false; setBusy(false); }
  }
  function load(event: FormEvent) {
    event.preventDefault();
    const id = sessionId.trim();
    if (id) void perform(`/api/skill-executions/${encodeURIComponent(id)}`);
  }
  function respond(choice: string) {
    if (!view || !pending || !available || !checked || busy) return;
    void perform(`/api/skill-executions/${encodeURIComponent(view.session_id)}/interactions/${encodeURIComponent(pending.id)}/respond`,
      { choice, approved: choice !== "CANCEL" && choice !== "UNABLE", preview_hash: pending.preview_hash });
  }

  return <section className="table-panel" aria-label="本地执行审批">
    <h3>本地执行审批</h3>
    <p>读取已有会话不会连接设备。审批不会立即执行；推进操作可能连接设备或修改配置，需单独点击。不会自动锁定结果。</p>
    <form onSubmit={load}>
      <label>本地执行会话 ID <input value={sessionId} disabled={busy} onChange={(e) => {
        setSessionId(e.target.value); setView(null); setChecked(false); setCleanupChecked(false); setError("");
      }} /></label>
      <button className="button button-primary" disabled={busy || !sessionId.trim()}>读取执行会话</button>
    </form>
    {error && <p role="alert">{error}</p>}
    {view && <>
      <p>当前状态：{view.status}</p><p>结果完整性：{view.integrity_status}</p>
      <p>Run：{view.test_run_id} · Result：{view.run_result_id}</p>
      {pending && <>
        <p>{pending.instructions}</p><p>动作：{pending.action_code ?? "人工确认"}</p>
        {missingPortPreview && <p role="alert">完整端口预览缺失，禁止审批。请重新读取。</p>}
        <section aria-label="端口影响预览">
          {pending.service_port_preview ? <>
            <PortOperations operations={pending.service_port_preview.operations} />
            {pending.service_port_preview.operations.length === 0 && <p>无待处理端口</p>}
            <p>保留消费者：{pending.service_port_preview.retained_consumers.join(" / ") || "无"}</p>
            <p>读取证据：{pending.service_port_preview.evidence_ids.join(" / ") || "无"}</p>
          </> : <dl>
            {Object.entries(pending.target).map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{value}</dd></div>)}
            <dt>影响端口</dt><dd>{pending.affected_service_ports.join(" / ") || "无"}</dd>
          </dl>}
          <p>审批 hash：<span className="mono">{pending.preview_hash}</span></p>
        </section>
        <label><input type="checkbox" checked={checked} disabled={busy || !available}
          onChange={(e) => setChecked(e.target.checked)} />我已核对目标和完整影响范围</label>
        <div className="row-actions">{pending.options.map((choice) => <button key={choice} type="button"
          className="button button-quiet" disabled={busy || !available || !checked}
          onClick={() => respond(choice)}>{choice === "CONFIRM" ? "确认审批" : choice === "CANCEL" ? "取消" : choice}</button>)}</div>
      </>}
      {cleanupAvailable && <button type="button" className="button button-quiet" disabled={busy}
        onClick={() => void perform(`/api/skill-executions/${encodeURIComponent(view.session_id)}/cleanup-preview`, {})}>
        预览本次端口清理（只读查询）</button>}
      {cleanupAvailable && view.cleanup_preview && <section aria-label="本次端口清理预览">
        <h4>删除本次创建端口，不恢复 WAN</h4>
        <PortOperations operations={view.cleanup_preview.operations} />
        <p>保留消费者：{view.cleanup_preview.retained_consumers.join(" / ") || "无"}</p>
        <p>读取证据：{view.cleanup_preview.evidence_ids.join(" / ") || "无"}</p>
        <p>审批 hash：<span className="mono">{view.cleanup_preview.preview_hash}</span></p>
        {view.cleanup_preview.operations.length === 0 ? <p>无可清理的本次创建端口</p> : <>
          <label><input type="checkbox" checked={cleanupChecked} disabled={busy}
            onChange={(e) => setCleanupChecked(e.target.checked)} />我确认删除上述本会话创建端口，且不代表恢复 WAN</label>
          <button type="button" className="button button-danger" disabled={busy || !cleanupChecked} onClick={() => {
            if (cleanupChecked && view.cleanup_preview) void perform(`/api/skill-executions/${encodeURIComponent(view.session_id)}/cleanup-execute`,
              { approved: true, preview_hash: view.cleanup_preview.preview_hash });
          }}>确认执行本次端口清理</button>
        </>}
      </section>}
      {view.cleanup_outcome && <section aria-label="本次端口清理结果">
        <p>清理结果：{view.cleanup_outcome.status}</p>
        <ul>{view.cleanup_outcome.items.map((item) => <li key={item.port_id}>{item.port_id}：{item.status}</li>)}</ul>
        <p>清理完成不代表 WAN 恢复；请人工核对，不会自动继续测试。</p>
      </section>}
      {!pending && editable && ["CREATED", "RUNNING"].includes(view.status) && <button type="button"
        className="button button-primary" disabled={busy} onClick={() => {
          if (window.confirm("推进可能连接设备或执行已审批的配置动作。确认仅推进当前会话的一步？")) {
            void perform(`/api/skill-executions/${encodeURIComponent(view.session_id)}/advance`, {});
          }
        }}>推进一步（可能操作设备）</button>}
    </>}
  </section>;
}
