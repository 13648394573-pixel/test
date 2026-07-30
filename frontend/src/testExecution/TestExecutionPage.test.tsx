import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { Device, DeviceApi } from "../devices/types";
import type { TestCase, TestCaseApi } from "../testCases/types";
import TestExecutionPage from "./TestExecutionPage";
import type {
  ExecutionResultValue,
  RunResult,
  TestExecutionApi,
  TestProject,
  TestProjectInput,
  TestRun
} from "./types";


const DEVICE: Device = {
  id: "device-1",
  device_type: "ONU",
  vendor: "Example",
  model: "X1",
  serial_number: "ONU0001",
  mac_address: "00:11:22:33:44:55",
  hardware_version: "A1",
  software_version: "1.0",
  created_at: "2026-07-29T08:00:00",
  updated_at: "2026-07-29T08:00:00"
};

const TEST_CASE: TestCase = {
  id: "case-1",
  case_code: "ONU-WAN-001",
  title: "Verify IPoE WAN",
  device_type: "ONU",
  category: "WAN",
  priority: "P1",
  preconditions: "ONU is registered",
  description: null,
  enabled: true,
  created_at: "2026-07-29T08:00:00",
  updated_at: "2026-07-29T08:00:00",
  steps: [
    {
      id: "step-1",
      test_case_id: "case-1",
      step_number: 1,
      action: "Create an IPoE WAN",
      expected_result: "WAN obtains an address",
      created_at: "2026-07-29T08:00:00",
      updated_at: "2026-07-29T08:00:00"
    }
  ]
};

const PROJECT: TestProject = {
  id: "project-1",
  name: "ONU Release",
  version: "R1",
  description: "Release acceptance",
  created_at: "2026-07-29T08:00:00",
  updated_at: "2026-07-29T08:00:00",
  case_selections: [{ case_source_id: "case-1" }]
};

const emptyDeviceApi: DeviceApi = {
  list: async () => [DEVICE],
  create: async () => { throw new Error("not used"); },
  update: async () => { throw new Error("not used"); },
  delete: async () => undefined
};

const emptyCaseApi: TestCaseApi = {
  list: async () => [TEST_CASE],
  create: async () => { throw new Error("not used"); },
  update: async () => { throw new Error("not used"); },
  delete: async () => undefined
};


class MemoryExecutionApi implements TestExecutionApi {
  projects: TestProject[];
  runs: TestRun[];

  constructor(projects: TestProject[] = [], runs: TestRun[] = []) {
    this.projects = structuredClone(projects);
    this.runs = structuredClone(runs);
  }

  async listProjects() {
    return structuredClone(this.projects);
  }

  async createProject(input: TestProjectInput) {
    const project = this.buildProject(`project-${this.projects.length + 1}`, input);
    this.projects.unshift(project);
    return structuredClone(project);
  }

  async updateProject(id: string, input: TestProjectInput) {
    const project = this.buildProject(id, input);
    this.projects = this.projects.map((candidate) =>
      candidate.id === id ? project : candidate
    );
    return structuredClone(project);
  }

  async deleteProject(id: string) {
    this.projects = this.projects.filter((project) => project.id !== id);
  }

  async createRun(projectId: string, deviceSourceId: string) {
    const run = buildRun(`run-${this.runs.length + 1}`, projectId, deviceSourceId);
    this.runs.unshift(run);
    return structuredClone(run);
  }

  async getRun(runId: string) {
    return structuredClone(this.runs.find((run) => run.id === runId)!);
  }

  async listRuns(projectId: string) {
    return structuredClone(
      this.runs.filter((run) => run.project_id === projectId)
    );
  }

  async updateResult(
    runId: string,
    resultId: string,
    result: ExecutionResultValue
  ) {
    const run = this.runs.find((candidate) => candidate.id === runId)!;
    const runResult = run.results.find((candidate) => candidate.id === resultId)!;
    runResult.result = result;
    runResult.executed_at = "2026-07-29T09:30:00";
    if (run.results.every((candidate) => candidate.result !== null)) {
      run.status = "COMPLETED";
      run.finished_at = "2026-07-29T09:30:00";
    }
    return structuredClone(runResult);
  }

  private buildProject(id: string, input: TestProjectInput): TestProject {
    return {
      id,
      name: input.name,
      version: input.version,
      description: input.description,
      case_selections: input.case_source_ids.map((case_source_id) => ({
        case_source_id
      })),
      created_at: "2026-07-29T09:00:00",
      updated_at: "2026-07-29T09:00:00"
    };
  }
}


function buildRun(
  id = "run-1",
  projectId = "project-1",
  deviceSourceId = "device-1"
): TestRun {
  return {
    id,
    project_id: projectId,
    device_source_id: deviceSourceId,
    device_snapshot: {
      device_type: DEVICE.device_type,
      vendor: DEVICE.vendor,
      model: DEVICE.model,
      serial_number: DEVICE.serial_number,
      mac_address: DEVICE.mac_address,
      hardware_version: DEVICE.hardware_version,
      software_version: DEVICE.software_version
    },
    snapshot_version: 1,
    status: "IN_PROGRESS",
    started_at: "2026-07-29T09:00:00",
    finished_at: null,
    results: [
      {
        id: `${id}-result-1`,
        run_id: id,
        case_source_id: TEST_CASE.id,
        case_snapshot: {
          case_code: TEST_CASE.case_code,
          title: TEST_CASE.title,
          device_type: TEST_CASE.device_type,
          category: TEST_CASE.category,
          priority: TEST_CASE.priority,
          preconditions: TEST_CASE.preconditions,
          description: TEST_CASE.description,
          enabled: TEST_CASE.enabled,
          steps: TEST_CASE.steps.map((step) => ({
            step_number: step.step_number,
            action: step.action,
            expected_result: step.expected_result
          }))
        },
        snapshot_version: 1,
        result: null,
        executed_at: null
      }
    ]
  };
}


afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});


describe("Test Execution", () => {
  it("creates, edits, and deletes a project with selected cases", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const api = new MemoryExecutionApi();
    render(
      <TestExecutionPage
        api={api}
        deviceApi={emptyDeviceApi}
        testCaseApi={emptyCaseApi}
      />
    );

    fireEvent.click(await screen.findByRole("button", { name: "新建测试项目" }));
    fireEvent.change(screen.getByLabelText("项目名称"), {
      target: { value: "ONU Release" }
    });
    fireEvent.change(screen.getByLabelText("版本"), {
      target: { value: "R1" }
    });
    fireEvent.click(screen.getByRole("checkbox", { name: /ONU-WAN-001/ }));
    fireEvent.click(screen.getByRole("button", { name: "保存项目" }));

    const row = await screen.findByRole("row", { name: /ONU Release/ });
    expect(within(row).getByText("1")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "编辑 ONU Release" }));
    fireEvent.change(screen.getByLabelText("版本"), {
      target: { value: "R2" }
    });
    fireEvent.click(screen.getByRole("button", { name: "保存项目" }));
    await waitFor(() => expect(screen.getByText("R2")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: "删除 ONU Release" }));
    await waitFor(() =>
      expect(screen.queryByRole("row", { name: /ONU Release/ })).not.toBeInTheDocument()
    );
  });

  it("creates a run from a selected device and renders immutable snapshots", async () => {
    const api = new MemoryExecutionApi([PROJECT]);
    render(
      <TestExecutionPage
        api={api}
        deviceApi={emptyDeviceApi}
        testCaseApi={emptyCaseApi}
      />
    );

    fireEvent.click(await screen.findByRole("button", { name: "打开 ONU Release" }));
    fireEvent.change(screen.getByLabelText("执行设备"), {
      target: { value: DEVICE.id }
    });
    fireEvent.click(screen.getByRole("button", { name: "创建执行" }));

    expect((await screen.findAllByText("ONU0001")).length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText("ONU-WAN-001")).toBeInTheDocument();
    expect(screen.getByText("Create an IPoE WAN")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "ONU0001" }).parentElement)
      .toHaveTextContent("快照版本 1");
    expect(screen.getByText("ONU-WAN-001").parentElement?.parentElement)
      .toHaveTextContent("快照版本 1");
  });

  it.each(["PASS", "FAIL", "BLOCKED"] as const)(
    "saves a %s result",
    async (value) => {
      const run = buildRun();
      const api = new MemoryExecutionApi([PROJECT], [run]);
      render(
        <TestExecutionPage
          api={api}
          deviceApi={emptyDeviceApi}
          testCaseApi={emptyCaseApi}
        />
      );

      fireEvent.click(await screen.findByRole("button", { name: "打开 ONU Release" }));
      fireEvent.click(await screen.findByRole("button", { name: /查看运行 run-1/ }));
      fireEvent.click(
        await screen.findByRole("button", {
          name: `设置 ONU-WAN-001 为 ${value}`
        })
      );

      await waitFor(() =>
        expect(screen.getByText(`结果：${value}`)).toBeInTheDocument()
      );
      expect(screen.getAllByText("已完成")).toHaveLength(2);
    }
  );
});
