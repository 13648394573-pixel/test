export type TestCasePriority = "P0" | "P1" | "P2" | "P3";

export interface CaseStepInput {
  action: string;
  expected_result: string;
}

export interface CaseStep extends CaseStepInput {
  id: string;
  test_case_id: string;
  step_number: number;
  created_at: string;
  updated_at: string;
}

export interface TestCaseInput {
  case_code: string;
  title: string;
  device_type: string | null;
  category: string;
  priority: TestCasePriority;
  preconditions: string | null;
  description: string | null;
  enabled: boolean;
  steps: CaseStepInput[];
}

export interface TestCase
  extends Omit<TestCaseInput, "steps"> {
  id: string;
  created_at: string;
  updated_at: string;
  steps: CaseStep[];
}

export interface TestCaseApi {
  list(): Promise<TestCase[]>;
  create(input: TestCaseInput): Promise<TestCase>;
  update(id: string, input: TestCaseInput): Promise<TestCase>;
  delete(id: string): Promise<void>;
}
