import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import type { Defect } from "../defects/types";
import type { DeviceApi } from "../devices/types";
import type { EnvironmentApi } from "../environments/types";
import FocusedRegressionPanel from "./FocusedRegressionPanel";
import type {
  FocusedRegressionApi,
  FocusedRegressionInput,
  FocusedRegressionRun
} from "./types";


const DEFECT = {
  id: "defect-1",
  defect_code: "DEF-000001",
  title: "WAN recovery failed",
  description: "No address",
  reproduction_steps: "Reconnect WAN",
  severity: "S2",
  status: "RESOLVED",
  resolution_notes: "Profile corrected",
  source_run_result_id: "result-source",
  created_at: "2026-08-10T08:00:00",
  updated_at: "2026-08-10T09:00:00",
  resolved_at: "2026-08-10T09:00:00",
  closed_at: null,
  source_run_result: buildResult("result-source", "FAIL"),
  regressions: []
} satisfies Defect;

const FOCUSED = {
  id: "focused-1",
  test_run_id: "run-focused-1",
  defect_id: DEFECT.id,
  source_run_result_id: DEFECT.source_run_result_id,
  defect_snapshot: {
    defect_code: DEFECT.defect_code,
    title: DEFECT.title,
    severity: DEFECT.severity,
    status: "RESOLVED",
    resolution_notes: DEFECT.resolution_notes,
    source_run_result_id: DEFECT.source_run_result_id,
    captured_at: "2026-08-10T10:00:00"
  },
  snapshot_version: 1,
  created_at: "2026-08-10T10:00:00",
  test_run: {
    id: "run-focused-1",
    project_id: "project-1",
    device_source_id: "device-1",
    device_snapshot: {
      device_type: "ONU",
      vendor: "Huawei",
      model: "HN8546X6",
      serial_number: "ONU-001",
      mac_address: null,
      hardware_version: "V1",
      software_version: "V2"
    },
    snapshot_version: 1,
    status: "IN_PROGRESS",
    started_at: "2026-08-10T10:00:00",
    finished_at: null,
    results: [buildResult("result-focused", null, "run-focused-1")],
    environment_snapshot: null
  }
} satisfies FocusedRegressionRun;


class MemoryFocusedApi implements FocusedRegressionApi {
  items: FocusedRegressionRun[] = [];
  lastInput: FocusedRegressionInput | null = null;

  async create(_defectId: string, input: FocusedRegressionInput) {
    this.lastInput = input;
    this.items = [structuredClone(FOCUSED)];
    return structuredClone(FOCUSED);
  }

  async listForDefect() {
    return structuredClone(this.items);
  }

  async getByRun() {
    return structuredClone(FOCUSED);
  }
}

const deviceApi: DeviceApi = {
  list: async () => [{
    id: "device-1",
    device_type: "ONU",
    vendor: "Huawei",
    model: "HN8546X6",
    serial_number: "ONU-001",
    mac_address: null,
    hardware_version: "V1",
    software_version: "V2",
    created_at: "2026-08-10T08:00:00",
    updated_at: "2026-08-10T08:00:00"
  }],
  create: async () => { throw new Error("not used"); },
  update: async () => { throw new Error("not used"); },
  delete: async () => undefined
};

const environmentApi: EnvironmentApi = {
  list: async () => [{
    id: "environment-1",
    name: "OLT Lab",
    description: null,
    enabled: true,
    created_at: "2026-08-10T08:00:00",
    updated_at: "2026-08-10T08:00:00",
    parameters: []
  }],
  create: async () => { throw new Error("not used"); },
  update: async () => { throw new Error("not used"); },
  delete: async () => undefined
};


afterEach(cleanup);


describe("FocusedRegressionPanel", () => {
  it("creates a new run from the resolved defect and tracks it", async () => {
    const api = new MemoryFocusedApi();
    render(
      <FocusedRegressionPanel
        defect={DEFECT}
        api={api}
        deviceApi={deviceApi}
        environmentApi={environmentApi}
      />
    );

    fireEvent.change(await screen.findByLabelText("执行设备"), {
      target: { value: "device-1" }
    });
    fireEvent.change(screen.getByLabelText("环境模板"), {
      target: { value: "environment-1" }
    });
    fireEvent.click(screen.getByRole("button", { name: "创建精简回归" }));

    await waitFor(() => expect(api.lastInput).toEqual({
      device_source_id: "device-1",
      environment_profile_id: "environment-1",
      source_run_result_id: "result-source"
    }));
    expect(await screen.findByText("run-focused-1")).toBeInTheDocument();
    expect(screen.getByText("执行中")).toBeInTheDocument();
    expect(screen.getByText("FOCUSED-WAN-001")).toBeInTheDocument();
  });
});


function buildResult(
  id: string,
  result: "PASS" | "FAIL" | "BLOCKED" | null,
  runId = "run-source"
) {
  return {
    id,
    run_id: runId,
    case_source_id: "case-wan",
    case_snapshot: {
      case_code: "FOCUSED-WAN-001",
      title: "Verify WAN recovery",
      device_type: "ONU",
      category: "WAN",
      priority: "P1",
      preconditions: null,
      description: null,
      enabled: true,
      steps: []
    },
    snapshot_version: 1,
    result,
    integrity_status: result === null ? "DRAFT" as const : "LOCKED" as const,
    actual_result: result === "FAIL" ? "No address" : null,
    blocked_reason: null,
    test_notes: null,
    executed_at: result === null ? null : "2026-08-10T08:00:00",
    locked_at: result === null ? null : "2026-08-10T08:00:00"
  };
}
