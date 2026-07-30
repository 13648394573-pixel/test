export type ExecutionResultValue = "PASS" | "FAIL" | "BLOCKED";
export type IntegrityStatus = "DRAFT" | "LOCKED";
export type EvidenceCategory = "SCREENSHOT" | "LOG" | "CONFIG" | "OTHER";

export interface Evidence {
  id: string;
  run_result_id: string | null;
  defect_id: string | null;
  category: EvidenceCategory;
  original_name: string;
  storage_path: string;
  media_type: string;
  file_size: number;
  sha256: string;
  description: string | null;
  created_at: string;
}

export interface ResultDraftInput {
  result?: ExecutionResultValue | null;
  actual_result?: string | null;
  blocked_reason?: string | null;
  test_notes?: string | null;
}

export interface TestProjectInput {
  name: string;
  version: string;
  description: string | null;
  case_source_ids: string[];
}

export interface ProjectCaseSelection {
  case_source_id: string;
}

export interface TestProject {
  id: string;
  name: string;
  version: string;
  description: string | null;
  created_at: string;
  updated_at: string;
  case_selections: ProjectCaseSelection[];
}

export interface DeviceSnapshot {
  device_type: string;
  vendor: string;
  model: string;
  serial_number: string;
  mac_address: string | null;
  hardware_version: string | null;
  software_version: string | null;
}

export interface CaseStepSnapshot {
  step_number: number;
  action: string;
  expected_result: string;
}

export interface CaseSnapshot {
  case_code: string;
  title: string;
  device_type: string | null;
  category: string;
  priority: string;
  preconditions: string | null;
  description: string | null;
  enabled: boolean;
  steps: CaseStepSnapshot[];
}

export interface RunResult {
  id: string;
  run_id: string;
  case_source_id: string;
  case_snapshot: CaseSnapshot;
  snapshot_version: number;
  result: ExecutionResultValue | null;
  integrity_status: IntegrityStatus;
  actual_result: string | null;
  blocked_reason: string | null;
  test_notes: string | null;
  executed_at: string | null;
  locked_at: string | null;
}

export interface TestRun {
  id: string;
  project_id: string;
  device_source_id: string;
  device_snapshot: DeviceSnapshot;
  snapshot_version: number;
  status: "IN_PROGRESS" | "COMPLETED";
  started_at: string;
  finished_at: string | null;
  results: RunResult[];
}

export interface TestExecutionApi {
  listProjects(): Promise<TestProject[]>;
  createProject(input: TestProjectInput): Promise<TestProject>;
  updateProject(id: string, input: TestProjectInput): Promise<TestProject>;
  deleteProject(id: string): Promise<void>;
  createRun(projectId: string, deviceSourceId: string): Promise<TestRun>;
  getRun(runId: string): Promise<TestRun>;
  listRuns(projectId: string): Promise<TestRun[]>;
  updateResult(
    runId: string,
    resultId: string,
    input: ResultDraftInput
  ): Promise<RunResult>;
  lockResult(runId: string, resultId: string): Promise<RunResult>;
  listResultEvidence(resultId: string): Promise<Evidence[]>;
  uploadResultEvidence(
    resultId: string,
    category: EvidenceCategory,
    file: File,
    description: string | null
  ): Promise<Evidence>;
  deleteEvidence(evidenceId: string): Promise<void>;
  evidenceDownloadUrl(evidenceId: string): string;
}
