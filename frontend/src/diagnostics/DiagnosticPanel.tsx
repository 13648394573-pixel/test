import { useEffect, useRef, useState } from "react";

import { diagnosticApi as defaultApi } from "./api";
import type { DiagnosticApi, DiagnosticInput, DiagnosticSession } from "./types";

interface DiagnosticPanelProps { resultId: string; locked: boolean; api?: DiagnosticApi; }

const DEFAULT_INPUT: DiagnosticInput = {
  wan_mode: "IPOE", gateway_target: "192.168.1.1", public_ip_target: "1.1.1.1",
  domain_target: "example.com", packet_count: 3, timeout_seconds: 5,
  max_attempts_per_layer: 2
};

export default function DiagnosticPanel({ resultId, locked, api = defaultApi }: DiagnosticPanelProps) {
  const [input, setInput] = useState(DEFAULT_INPUT);
  const [sessions, setSessions] = useState<DiagnosticSession[]>([]);
  const [error, setError] = useState("");
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    api.list(resultId).then(setSessions).catch((reason: Error) => setError(reason.message));
    return () => { mounted.current = false; };
  }, [api, resultId]);

  const replace = (session: DiagnosticSession) => {
    setSessions((current) => [session, ...current.filter((item) => item.id !== session.id)]);
  };
  const poll = async (sessionId: string) => {
    const session = await api.get(sessionId);
    if (!mounted.current) return;
    replace(session);
    if (session.status === "PENDING" || session.status === "RUNNING") {
      window.setTimeout(() => void poll(sessionId).catch((reason: Error) => setError(reason.message)), 1000);
    }
  };
  const start = async () => {
    try {
      setError("");
      const session = await api.create(resultId, input);
      replace(session);
      if (session.status === "PENDING" || session.status === "RUNNING") await poll(session.id);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Ping诊断失败");
    }
  };

  return <section className="diagnostic-panel" aria-label="Ping诊断">
    <h4>Ping诊断</h4>
    <label>WAN类型<select disabled={locked} value={input.wan_mode} onChange={(event) =>
      setInput((current) => ({ ...current, wan_mode: event.target.value as "IPOE" | "PPPOE" }))}>
      <option value="IPOE">IPoE</option><option value="PPPOE">PPPoE</option>
    </select></label>
    <button type="button" disabled={locked} onClick={start}>开始Ping诊断</button>
    {locked && <p>结果已锁定，仅可查看已有诊断。</p>}
    {error && <p role="alert">{error}</p>}
    {sessions.map((session) => <article key={session.id}>
      <strong>{session.adapter_key} · {session.wan_mode} · {session.status}</strong>
      {session.error_message && <p>{session.error_message}</p>}
      <table><thead><tr><th>层级</th><th>目标</th><th>尝试</th><th>结果</th><th>收/发</th><th>证据</th></tr></thead>
        <tbody>{session.attempts.map((attempt) => <tr key={attempt.id}>
          <td>{attempt.layer}</td><td>{attempt.target}</td><td>{attempt.attempt_number}</td>
          <td>{attempt.status}</td><td>{attempt.packets_received}/{attempt.packets_sent}</td>
          <td>{attempt.evidence_links.map((link) => <a key={link.evidence_id}
            href={`/api/evidences/${link.evidence_id}/download`}>诊断证据</a>)}</td>
        </tr>)}</tbody></table>
    </article>)}
  </section>;
}
