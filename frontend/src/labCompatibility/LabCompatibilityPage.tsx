import { useEffect, useMemo, useState } from "react";

import type {
  CompatibilityCheck,
  CompatibilityCheckInput,
  CompatibilityEvidence,
  LabCompatibilityApi,
  StageStatus
} from "./types";

interface Props {
  api: LabCompatibilityApi;
}

const STATUS_LABEL: Record<StageStatus, string> = {
  VERIFIED: "已验证",
  NEEDS_INPUT: "需补充",
  BLOCKED: "受阻",
  NOT_RUN: "未执行"
};

const STAGE_LABEL: Record<string, string> = {
  LOCAL_ENV: "本机运行环境",
  OLT_CONNECT: "OLT 连接与主机指纹",
  OLT_AUTOFIND: "OLT 自动发现查询",
  OLT_CURRENT_STATE: "OLT 当前 ONU/WAN 状态",
  ONU_WEB_WAN: "ONU Web WAN 页面",
  ONU_WEB_PING_PAGE: "ONU Web Ping 页面",
  PC_INTERFACE: "电脑指定网卡",
  PC_PING: "电脑侧基础 Ping"
};

const initialForm = {
  olt_host: "",
  olt_port: "22",
  olt_username_ref: "olt.lab.username",
  olt_password_ref: "olt.lab.password",
  onu_serial_number: "",
  frame: "",
  slot: "",
  pon_port: "",
  ont_id: "",
  onu_web_url: "",
  onu_web_username_ref: "onu.lab.username",
  onu_web_password_ref: "onu.lab.password",
  pc_interface_name: "",
  pc_source_address: "",
  pc_ping_target: ""
};

type FormState = typeof initialForm;
type CredentialKey = "olt_username_ref" | "olt_password_ref" | "onu_web_username_ref" | "onu_web_password_ref";

const credentialRows: Array<{ key: CredentialKey; label: string }> = [
  { key: "olt_username_ref", label: "OLT 用户名" },
  { key: "olt_password_ref", label: "OLT 密码" },
  { key: "onu_web_username_ref", label: "ONU Web 用户名" },
  { key: "onu_web_password_ref", label: "ONU Web 密码" }
];

function optionalNumber(value: string): number | null {
  return value.trim() === "" ? null : Number(value);
}

export default function LabCompatibilityPage({ api }: Props) {
  const [form, setForm] = useState<FormState>(initialForm);
  const [fingerprint, setFingerprint] = useState("");
  const [fingerprintConfirmed, setFingerprintConfirmed] = useState(false);
  const [credentialSecrets, setCredentialSecrets] = useState<Record<CredentialKey, string>>({
    olt_username_ref: "",
    olt_password_ref: "",
    onu_web_username_ref: "",
    onu_web_password_ref: ""
  });
  const [credentialReady, setCredentialReady] = useState<Record<CredentialKey, boolean>>({
    olt_username_ref: false,
    olt_password_ref: false,
    onu_web_username_ref: false,
    onu_web_password_ref: false
  });
  const [credentialChecked, setCredentialChecked] = useState<Record<CredentialKey, boolean>>({
    olt_username_ref: false,
    olt_password_ref: false,
    onu_web_username_ref: false,
    onu_web_password_ref: false
  });
  const [check, setCheck] = useState<CompatibilityCheck | null>(null);
  const [evidence, setEvidence] = useState<CompatibilityEvidence[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const targetFields = [form.frame, form.slot, form.pon_port, form.ont_id];
  const targetComplete = targetFields.every(Boolean) || targetFields.every((value) => !value);
  const canRun = useMemo(
    () => Boolean(
      fingerprint && fingerprintConfirmed && targetComplete && form.olt_host &&
      form.onu_web_url && form.pc_interface_name && form.pc_source_address &&
      form.pc_ping_target && credentialRows.every(({ key }) => form[key]) && !busy
    ),
    [busy, fingerprint, fingerprintConfirmed, form, targetComplete]
  );

  useEffect(() => {
    if (!check || check.lifecycle === "COMPLETED") return;
    const timer = window.setTimeout(async () => {
      try {
        setCheck(await api.getCheck(check.check_id));
      } catch (reason) {
        setError(reason instanceof Error ? reason.message : "读取检查状态失败");
      }
    }, 750);
    return () => window.clearTimeout(timer);
  }, [api, check]);

  useEffect(() => {
    if (!check || check.lifecycle !== "COMPLETED") return;
    api.listEvidence(check.check_id).then(setEvidence).catch(() => setEvidence([]));
    setBusy(false);
  }, [api, check]);

  function update(key: keyof FormState, value: string) {
    setForm((current) => ({ ...current, [key]: value }));
    if (credentialRows.some((row) => row.key === key)) {
      const credentialKey = key as CredentialKey;
      setCredentialReady((current) => ({ ...current, [credentialKey]: false }));
      setCredentialChecked((current) => ({ ...current, [credentialKey]: false }));
    }
    if (key === "olt_host" || key === "olt_port") {
      setFingerprint("");
      setFingerprintConfirmed(false);
    }
  }

  async function previewFingerprint() {
    setError("");
    try {
      setFingerprint(await api.previewHostKey(form.olt_host, Number(form.olt_port)));
      setFingerprintConfirmed(false);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "无法读取 OLT 主机指纹");
    }
  }

  async function saveCredential(key: CredentialKey) {
    const secret = credentialSecrets[key];
    if (!secret) return;
    try {
      const result = await api.enrollCredential(form[key], secret);
      setCredentialReady((current) => ({ ...current, [key]: result.available }));
      setCredentialChecked((current) => ({ ...current, [key]: true }));
      setCredentialSecrets((current) => ({ ...current, [key]: "" }));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "凭据保存失败");
    }
  }

  async function checkCredential(key: CredentialKey) {
    try {
      const result = await api.credentialStatus(form[key]);
      setCredentialReady((current) => ({ ...current, [key]: result.available }));
      setCredentialChecked((current) => ({ ...current, [key]: true }));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "凭据状态检查失败");
    }
  }

  async function startCheck() {
    if (!canRun) return;
    setBusy(true);
    setError("");
    const input: CompatibilityCheckInput = {
      olt_host: form.olt_host,
      olt_port: Number(form.olt_port),
      expected_host_key_fingerprint: fingerprint,
      olt_username_ref: form.olt_username_ref,
      olt_password_ref: form.olt_password_ref,
      onu_serial_number: form.onu_serial_number || null,
      frame: optionalNumber(form.frame),
      slot: optionalNumber(form.slot),
      pon_port: optionalNumber(form.pon_port),
      ont_id: optionalNumber(form.ont_id),
      onu_web_url: form.onu_web_url,
      onu_web_username_ref: form.onu_web_username_ref,
      onu_web_password_ref: form.onu_web_password_ref,
      onu_adapter_key: "neutral-v1",
      pc_interface_name: form.pc_interface_name,
      pc_source_address: form.pc_source_address,
      pc_ping_target: form.pc_ping_target
    };
    try {
      setCheck(await api.createCheck(input));
    } catch (reason) {
      setBusy(false);
      setError(reason instanceof Error ? reason.message : "无法启动现场检查");
    }
  }

  return (
    <section className="lab-compatibility" aria-labelledby="lab-compatibility-title">
      <div className="page-heading">
        <div>
          <p className="section-kicker">Read-only Lab Check</p>
          <h2 id="lab-compatibility-title">现场兼容性检查</h2>
          <p>在正式注册和 WAN 下发前，先确认本机、OLT、ONU Web 和测试网卡兼容。</p>
        </div>
      </div>

      <div className="lab-safety" role="note">
        本流程不会注册 ONU、不会下发 WAN、不会修改 OLT 配置，也不会执行 ONU Web Ping。
      </div>
      {error && <p className="form-error" role="alert">{error}</p>}

      <div className="lab-step">
        <h3><span>1</span> 填写目标</h3>
        <div className="lab-grid">
          <label>OLT 地址<input value={form.olt_host} onChange={(e) => update("olt_host", e.target.value)} /></label>
          <label>OLT 端口<input type="number" value={form.olt_port} onChange={(e) => update("olt_port", e.target.value)} /></label>
          <label>ONU SN（可选）<input value={form.onu_serial_number} onChange={(e) => update("onu_serial_number", e.target.value)} /></label>
          <label>ONU Web 地址<input value={form.onu_web_url} onChange={(e) => update("onu_web_url", e.target.value)} /></label>
          <label>Frame<input type="number" value={form.frame} onChange={(e) => update("frame", e.target.value)} /></label>
          <label>Slot<input type="number" value={form.slot} onChange={(e) => update("slot", e.target.value)} /></label>
          <label>PON 端口<input type="number" value={form.pon_port} onChange={(e) => update("pon_port", e.target.value)} /></label>
          <label>ONT ID<input type="number" value={form.ont_id} onChange={(e) => update("ont_id", e.target.value)} /></label>
          <label>电脑网卡<input value={form.pc_interface_name} onChange={(e) => update("pc_interface_name", e.target.value)} /></label>
          <label>电脑源地址<input value={form.pc_source_address} onChange={(e) => update("pc_source_address", e.target.value)} /></label>
          <label>Ping 目标<input value={form.pc_ping_target} onChange={(e) => update("pc_ping_target", e.target.value)} /></label>
        </div>
        {!targetComplete && <p className="field-warning">Frame、Slot、PON 端口和 ONT ID 必须同时填写或全部留空。</p>}
        <div className="fingerprint-row">
          <button className="button" type="button" onClick={previewFingerprint} disabled={!form.olt_host}>读取主机指纹</button>
          {fingerprint && <code>{fingerprint}</code>}
          {fingerprint && <label className="confirm-line"><input type="checkbox" checked={fingerprintConfirmed} onChange={(e) => setFingerprintConfirmed(e.target.checked)} />我已核对 OLT 主机指纹</label>}
        </div>
      </div>

      <div className="lab-step">
        <h3><span>2</span> 检查凭据</h3>
        <p>秘密只写入 Windows 本机凭据保险箱，页面保存后立即清空。</p>
        <div className="credential-list">
          {credentialRows.map(({ key, label }) => (
            <div className="credential-row" key={key}>
              <label>{label}引用<input value={form[key]} onChange={(e) => update(key, e.target.value)} /></label>
              <label>{label}秘密<input type="password" value={credentialSecrets[key]} onChange={(e) => setCredentialSecrets((current) => ({ ...current, [key]: e.target.value }))} /></label>
              <button className="button" type="button" onClick={() => checkCredential(key)}>检查已有凭据</button>
              <button className="button" type="button" onClick={() => saveCredential(key)}>保存到本机</button>
              <span>{credentialReady[key] ? "本机已有" : credentialChecked[key] ? "本机未找到" : "待确认"}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="lab-step">
        <h3><span>3</span> 执行检查</h3>
        <button className="button button-primary" type="button" disabled={!canRun} onClick={startCheck}>开始只读检查</button>
        {check && <p>运行状态：{check.lifecycle === "COMPLETED" ? "已完成" : "正在检查"}</p>}
        <div className="stage-grid">
          {check?.stages.map((stage) => (
            <article className={`stage-card status-${stage.status.toLowerCase()}`} key={stage.code}>
              <div><strong>{STAGE_LABEL[stage.code] ?? stage.code}</strong><span>{STATUS_LABEL[stage.status]}</span></div>
              <p>{stage.message}</p>
            </article>
          ))}
        </div>
      </div>

      <div className="lab-step">
        <h3><span>4</span> 查看报告</h3>
        {check?.overall_status && <p className={`overall-status overall-${check.overall_status.toLowerCase()}`}>总体状态：{{ READY: "可以进入正式验证", PARTIAL: "部分能力需要补充", BLOCKED: "关键能力受阻" }[check.overall_status]}</p>}
        {evidence.length === 0 ? <p className="empty-state">完成检查后在此显示证据名称和校验值。</p> : (
          <ul className="evidence-list">{evidence.map((item) => <li key={`${item.storage_path}-${item.sha256}`}><span>{item.original_name}</span><code>{item.sha256}</code></li>)}</ul>
        )}
      </div>
    </section>
  );
}
