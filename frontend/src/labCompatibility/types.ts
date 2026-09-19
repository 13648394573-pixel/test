export type StageStatus = "VERIFIED" | "NEEDS_INPUT" | "BLOCKED" | "NOT_RUN";
export type OverallStatus = "READY" | "PARTIAL" | "BLOCKED";
export type Lifecycle = "PENDING" | "RUNNING" | "COMPLETED";

export interface CompatibilityEvidence {
  original_name: string;
  media_type: string;
  storage_path: string | null;
  file_size: number | null;
  sha256: string | null;
  redacted: boolean;
}

export interface CompatibilityStage {
  code: string;
  status: StageStatus;
  message: string;
  evidence: CompatibilityEvidence[];
}

export interface CompatibilityCheck {
  check_id: string;
  lifecycle: Lifecycle;
  overall_status: OverallStatus | null;
  stages: CompatibilityStage[];
  created_at: string;
  updated_at: string;
}

export interface CompatibilityCheckInput {
  olt_host: string;
  olt_port: number;
  expected_host_key_fingerprint: string;
  olt_username_ref: string;
  olt_password_ref: string;
  onu_serial_number: string | null;
  frame: number | null;
  slot: number | null;
  pon_port: number | null;
  ont_id: number | null;
  onu_web_url: string;
  onu_web_username_ref: string;
  onu_web_password_ref: string;
  onu_adapter_key: "neutral-v1";
  pc_interface_name: string;
  pc_source_address: string;
  pc_ping_target: string;
}

export interface CredentialAvailability {
  reference: string;
  available: boolean;
}

export interface LabCompatibilityApi {
  previewHostKey(host: string, port: number): Promise<string>;
  credentialStatus(reference: string): Promise<CredentialAvailability>;
  enrollCredential(reference: string, secret: string): Promise<CredentialAvailability>;
  createCheck(input: CompatibilityCheckInput): Promise<CompatibilityCheck>;
  getCheck(checkId: string): Promise<CompatibilityCheck>;
  listEvidence(checkId: string): Promise<CompatibilityEvidence[]>;
}
