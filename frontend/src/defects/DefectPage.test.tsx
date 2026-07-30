import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor
} from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import type {
  Evidence,
  TestExecutionApi,
  TestProject,
  TestRun
} from "../testExecution/types";
import DefectPage from "./DefectPage";
import type {
  Defect,
  DefectApi,
  DefectInput,
  DefectUpdate,
  RegressionInput
} from "./types";


const PROJECT: TestProject = {
  id: "project-1",
  name: "ONU Release",
  version: "R1",
  description: null,
  created_at: "2026-07-30T08:00:00",
  updated_at: "2026-07-30T08:00:00",
  case_selections: [{ case_source_id: "case-1" }]
};

const RUNS: TestRun[] = [
  buildRun("run-source", "result-source", "FAIL"),
  buildRun("run-pass", "result-pass", "PASS")
];


class MemoryDefectApi implements DefectApi {
  defects: Defect[] = [];

  async list() {
    return structuredClone(this.defects);
  }

  async get(id: string) {
    return structuredClone(this.defects.find((item) => item.id === id)!);
  }

  async create(input: DefectInput) {
    const source = RUNS.flatMap((run) => run.results).find(
      (result) => result.id === input.source_run_result_id
    )!;
    const defect = {
      id: "defect-1",
      defect_code: "DEF-000001",
      ...input,
      status: "OPEN",
      resolution_notes: null,
      created_at: "2026-07-30T09:00:00",
      updated_at: "2026-07-30T09:00:00",
      resolved_at: null,
      closed_at: null,
      source_run_result: source,
      regressions: []
    } satisfies Defect;
    this.defects = [defect];
    return structuredClone(defect);
  }

  async update(id: string, input: DefectUpdate) {
    Object.assign(this.defects.find((item) => item.id === id)!, input);
    return this.get(id);
  }

  async transition(
    id: string,
    targetStatus: Defect["status"],
    resolutionNotes: string | null
  ) {
    const defect = this.defects.find((item) => item.id === id)!;
    defect.status = targetStatus;
    if (targetStatus === "RESOLVED") {
      defect.resolution_notes = resolutionNotes;
      defect.resolved_at = "2026-07-30T10:00:00";
    }
    return this.get(id);
  }

  async listRegressions(id: string) {
    return structuredClone(
      this.defects.find((item) => item.id === id)!.regressions
    );
  }

  async createRegression(id: string, input: RegressionInput) {
    const defect = this.defects.find((item) => item.id === id)!;
    const evidence = RUNS.flatMap((run) => run.results).find(
      (result) => result.id === input.verification_run_result_id
    )!;
    const regression = {
      id: "regression-1",
      defect_id: id,
      verification_run_result_id: evidence.id,
      result: evidence.result!,
      notes: input.notes,
      executed_at: evidence.executed_at!,
      created_at: "2026-07-30T11:00:00",
      verification_run_result: evidence
    };
    defect.regressions.push(regression);
    defect.status = "CLOSED";
    defect.closed_at = "2026-07-30T11:00:00";
    return structuredClone(regression);
  }

  async listEvidence() {
    return [];
  }

  async uploadEvidence(): Promise<Evidence> {
    throw new Error("not used");
  }

  async deleteEvidence() {
    return undefined;
  }

  evidenceDownloadUrl(id: string) {
    return `/api/evidences/${id}/download`;
  }
}


const executionApi: TestExecutionApi = {
  listProjects: async () => [PROJECT],
  listRuns: async () => structuredClone(RUNS),
  createProject: async () => { throw new Error("not used"); },
  updateProject: async () => { throw new Error("not used"); },
  deleteProject: async () => undefined,
  createRun: async () => { throw new Error("not used"); },
  getRun: async () => { throw new Error("not used"); },
  updateResult: async () => { throw new Error("not used"); },
  lockResult: async () => { throw new Error("not used"); },
  listResultEvidence: async () => [],
  uploadResultEvidence: async () => { throw new Error("not used"); },
  deleteEvidence: async () => undefined,
  evidenceDownloadUrl: (id) => `/api/evidences/${id}/download`
};


afterEach(cleanup);


describe("Defect & Regression", () => {
  it("completes create, edit, resolve and PASS regression flow", async () => {
    const api = new MemoryDefectApi();
    render(<DefectPage api={api} executionApi={executionApi} />);

    fireEvent.click(
      await screen.findByRole("button", { name: "新建缺陷" })
    );
    fireEvent.change(screen.getByLabelText("失败证据"), {
      target: { value: "result-source" }
    });
    fireEvent.change(screen.getByLabelText("标题"), {
      target: { value: "WAN does not recover" }
    });
    fireEvent.change(screen.getByLabelText("现象说明"), {
      target: { value: "WAN remains disconnected" }
    });
    fireEvent.change(screen.getByLabelText("复现步骤"), {
      target: { value: "Reconnect the uplink" }
    });
    fireEvent.click(screen.getByRole("button", { name: "保存缺陷" }));

    expect(
      await screen.findByRole("button", { name: /打开 DEF-000001/ })
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /打开 DEF-000001/ }));
    expect(screen.getByText("ONU-WAN-001")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "编辑缺陷" }));
    fireEvent.change(screen.getByLabelText("标题"), {
      target: { value: "WAN recovery fails" }
    });
    fireEvent.click(screen.getByRole("button", { name: "保存缺陷" }));
    await waitFor(() =>
      expect(screen.getAllByText("WAN recovery fails")).toHaveLength(2)
    );

    fireEvent.click(screen.getByRole("button", { name: "开始处理" }));
    await screen.findByText("IN_PROGRESS");
    fireEvent.change(screen.getByLabelText("解决说明"), {
      target: { value: "Updated WAN handling" }
    });
    fireEvent.click(screen.getByRole("button", { name: "标记已解决" }));
    await screen.findByText("RESOLVED");

    fireEvent.change(screen.getByLabelText("回归证据"), {
      target: { value: "result-pass" }
    });
    fireEvent.click(screen.getByRole("button", { name: "记录回归" }));

    await waitFor(() => expect(screen.getByText("CLOSED")).toBeInTheDocument());
    expect(screen.getByText("PASS")).toBeInTheDocument();
    expect(api.defects[0].regressions).toHaveLength(1);
  });

  it("shows only FAIL/BLOCKED evidence that has no defect", async () => {
    const api = new MemoryDefectApi();
    render(<DefectPage api={api} executionApi={executionApi} />);

    fireEvent.click(
      await screen.findByRole("button", { name: "新建缺陷" })
    );

    const options = screen.getByLabelText("失败证据").querySelectorAll("option");
    expect(Array.from(options).map((option) => option.textContent)).toEqual([
      "请选择失败或阻塞结果",
      "ONU-WAN-001 · FAIL"
    ]);
  });
});


function buildRun(
  runId: string,
  resultId: string,
  result: "PASS" | "FAIL" | "BLOCKED"
): TestRun {
  return {
    id: runId,
    project_id: PROJECT?.id ?? "project-1",
    device_source_id: "device-1",
    device_snapshot: {
      device_type: "ONU",
      vendor: "Huawei",
      model: "HN8546X6",
      serial_number: "ONU-001",
      mac_address: null,
      hardware_version: "V1",
      software_version: "V5R020"
    },
    snapshot_version: 1,
    status: "COMPLETED",
    started_at: "2026-07-30T08:00:00",
    finished_at: "2026-07-30T08:30:00",
    results: [
      {
        id: resultId,
        run_id: runId,
        case_source_id: "case-1",
        case_snapshot: {
          case_code: "ONU-WAN-001",
          title: "Verify WAN recovery",
          device_type: "ONU",
          category: "WAN",
          priority: "P1",
          preconditions: null,
          description: null,
          enabled: true,
          steps: [
            {
              step_number: 1,
              action: "Reconnect WAN",
              expected_result: "WAN recovers"
            }
          ]
        },
        snapshot_version: 1,
        result,
        integrity_status: "LOCKED",
        actual_result: result === "FAIL" ? "WAN did not recover" : null,
        blocked_reason: result === "BLOCKED" ? "Lab unavailable" : null,
        test_notes: null,
        executed_at: "2026-07-30T08:30:00",
        locked_at: "2026-07-30T08:30:00"
      }
    ]
  };
}
