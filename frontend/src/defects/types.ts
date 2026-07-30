import type {
  ExecutionResultValue,
  RunResult
} from "../testExecution/types";


export type Severity = "S1" | "S2" | "S3" | "S4";
export type DefectStatus =
  | "OPEN"
  | "IN_PROGRESS"
  | "RESOLVED"
  | "REOPENED"
  | "CLOSED";

export interface DefectInput {
  source_run_result_id: string;
  title: string;
  description: string;
  reproduction_steps: string;
  severity: Severity;
}

export interface DefectUpdate {
  title: string;
  description: string;
  reproduction_steps: string;
  severity: Severity;
}

export interface RegressionInput {
  verification_run_result_id: string;
  notes: string | null;
}

export interface Regression {
  id: string;
  defect_id: string;
  verification_run_result_id: string;
  result: ExecutionResultValue;
  notes: string | null;
  executed_at: string;
  created_at: string;
  verification_run_result: RunResult;
}

export interface Defect {
  id: string;
  defect_code: string;
  source_run_result_id: string;
  title: string;
  description: string;
  reproduction_steps: string;
  severity: Severity;
  status: DefectStatus;
  resolution_notes: string | null;
  created_at: string;
  updated_at: string;
  resolved_at: string | null;
  closed_at: string | null;
  source_run_result: RunResult;
  regressions: Regression[];
}

export interface DefectApi {
  list(status?: DefectStatus, severity?: Severity): Promise<Defect[]>;
  get(id: string): Promise<Defect>;
  create(input: DefectInput): Promise<Defect>;
  update(id: string, input: DefectUpdate): Promise<Defect>;
  transition(
    id: string,
    targetStatus: DefectStatus,
    resolutionNotes: string | null
  ): Promise<Defect>;
  listRegressions(id: string): Promise<Regression[]>;
  createRegression(id: string, input: RegressionInput): Promise<Regression>;
}
