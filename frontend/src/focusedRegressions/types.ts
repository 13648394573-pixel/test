import type { TestRun } from "../testExecution/types";


export interface FocusedRegressionInput {
  device_source_id: string;
  environment_profile_id: string;
  source_run_result_id: string | null;
}
export interface FocusedDefectSnapshot {
  defect_code: string;
  title: string;
  severity: string;
  status: string;
  resolution_notes: string | null;
  source_run_result_id: string;
  captured_at: string;
}

export interface FocusedRegressionRun {
  id: string;
  test_run_id: string;
  defect_id: string;
  source_run_result_id: string;
  defect_snapshot: FocusedDefectSnapshot;
  snapshot_version: number;
  created_at: string;
  test_run: TestRun;
}

export interface FocusedRegressionApi {
  create(
    defectId: string,
    input: FocusedRegressionInput
  ): Promise<FocusedRegressionRun>;
  listForDefect(defectId: string): Promise<FocusedRegressionRun[]>;
  getByRun(runId: string): Promise<FocusedRegressionRun>;
}
