export type DiagnosticStatus = "PENDING" | "RUNNING" | "COMPLETED" | "FAILED" | "INTERRUPTED";
export type DiagnosticLayer = "GATEWAY" | "PUBLIC_IP" | "DOMAIN";

export interface DiagnosticInput {
  wan_mode: "IPOE" | "PPPOE";
  adapter_key?: string | null;
  gateway_target: string;
  public_ip_target: string;
  domain_target: string;
  packet_count: number;
  timeout_seconds: number;
  max_attempts_per_layer: number;
}

export interface DiagnosticAttempt {
  id: string; sequence: number; layer: DiagnosticLayer; target: string;
  attempt_number: number; status: "PASS" | "FAIL" | "ERROR";
  packets_sent: number; packets_received: number; loss_percent: string | number;
  latency_min_ms: string | number | null; latency_avg_ms: string | number | null;
  latency_max_ms: string | number | null; raw_output: string; error_code: string | null;
  started_at: string; finished_at: string;
  evidence_links: Array<{ evidence_id: string }>;
}

export interface DiagnosticSession {
  id: string; run_result_id: string; retry_of_session_id: string | null;
  adapter_key: string; adapter_version: string; wan_mode: "IPOE" | "PPPOE";
  status: DiagnosticStatus; policy_snapshot: Record<string, unknown>;
  snapshot_version: number; error_code: string | null; error_message: string | null;
  created_at: string; started_at: string | null; completed_at: string | null;
  attempts: DiagnosticAttempt[];
}

export interface DiagnosticApi {
  create(resultId: string, input: DiagnosticInput): Promise<DiagnosticSession>;
  list(resultId: string): Promise<DiagnosticSession[]>;
  get(sessionId: string): Promise<DiagnosticSession>;
}
