export interface RunHistoryItem {
  id: string;
  run_no: string;
  project_id: string;
  project_name: string;
  project_version: string;
  device: {
    device_type: string | null;
    vendor: string | null;
    model: string | null;
    serial_number: string | null;
    software_version: string | null;
  };
  status: "IN_PROGRESS" | "COMPLETED";
  summary: { total: number; pass: number; fail: number; blocked: number; unset: number };
  started_at: string;
  finished_at: string | null;
}

export interface RunHistoryPage {
  items: RunHistoryItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface RunHistoryFilters {
  project_id?: string;
  run_no?: string;
  project_version?: string;
  device_type?: string;
  vendor?: string;
  model?: string;
  serial_number?: string;
  software_version?: string;
  status?: "IN_PROGRESS" | "COMPLETED" | "";
  result?: "PASS" | "FAIL" | "BLOCKED" | "UNSET" | "";
  started_from?: string;
  started_to?: string;
  limit?: number;
  offset?: number;
}

export interface RunComparison {
  runs: RunHistoryItem[];
  rows: Array<{
    case_code: string;
    title: string;
    base: { run_id: string; result: string | null; evidence_count: number };
    targets: Array<{ run_id: string; result: string | null; evidence_count: number; change: string }>;
  }>;
}

export interface RunHistoryApi {
  search(filters: RunHistoryFilters): Promise<RunHistoryPage>;
  compare(runIds: string[]): Promise<RunComparison>;
}
