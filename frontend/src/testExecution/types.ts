export type ExecutionResultValue = "PASS" | "FAIL" | "BLOCKED";

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
  executed_at: string | null;
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
    result: ExecutionResultValue
  ): Promise<RunResult>;
}
