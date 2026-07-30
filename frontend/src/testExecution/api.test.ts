import { afterEach, describe, expect, it, vi } from "vitest";

import { testExecutionApi } from "./api";
import type {
  TestProject,
  TestProjectInput,
  TestRun
} from "./types";


const projectInput: TestProjectInput = {
  name: "Release acceptance",
  version: "V1",
  description: null,
  case_source_ids: ["case-1"]
};

const project: TestProject = {
  id: "project-1",
  name: "Release acceptance",
  version: "V1",
  description: null,
  created_at: "2026-07-29T08:00:00",
  updated_at: "2026-07-29T08:00:00",
  case_selections: [{ case_source_id: "case-1" }]
};

const run: TestRun = {
  id: "run-1",
  project_id: "project-1",
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
  status: "IN_PROGRESS",
  started_at: "2026-07-29T09:00:00",
  finished_at: null,
  environment_snapshot: null,
  results: []
};


afterEach(() => {
  vi.unstubAllGlobals();
});


describe("testExecutionApi", () => {
  it("supports project CRUD contracts", async () => {
    const fetchStub = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify([project]), { status: 200 })
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify(project), { status: 201 })
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify(project), { status: 200 })
      )
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchStub);

    await testExecutionApi.listProjects();
    await testExecutionApi.createProject(projectInput);
    await testExecutionApi.updateProject("project-1", projectInput);
    await testExecutionApi.deleteProject("project-1");

    expect(fetchStub).toHaveBeenNthCalledWith(1, "/api/test-projects", {
      headers: { "Content-Type": "application/json" }
    });
    expect(fetchStub).toHaveBeenNthCalledWith(2, "/api/test-projects", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(projectInput)
    });
    expect(fetchStub).toHaveBeenNthCalledWith(
      3,
      "/api/test-projects/project-1",
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(projectInput)
      }
    );
    expect(fetchStub).toHaveBeenNthCalledWith(
      4,
      "/api/test-projects/project-1",
      {
        method: "DELETE",
        headers: { "Content-Type": "application/json" }
      }
    );
  });

  it("supports run creation, detail, history and result update", async () => {
    const fetchStub = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(run), { status: 201 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(run), { status: 200 }))
      .mockResolvedValueOnce(
        new Response(JSON.stringify([run]), { status: 200 })
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            id: "result-1",
            run_id: "run-1",
            case_source_id: "case-1",
            case_snapshot: {},
            snapshot_version: 1,
            result: "BLOCKED",
            executed_at: "2026-07-29T10:00:00"
          }),
          { status: 200 }
        )
      );
    vi.stubGlobal("fetch", fetchStub);

    await testExecutionApi.createRun("project-1", "device-1", "env-1");
    await testExecutionApi.getRun("run-1");
    await testExecutionApi.listRuns("project-1");
    await testExecutionApi.updateResult(
      "run-1",
      "result-1",
      { result: "BLOCKED" }
    );

    expect(fetchStub).toHaveBeenNthCalledWith(
      1,
      "/api/test-projects/project-1/runs",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          device_source_id: "device-1",
          environment_profile_id: "env-1"
        })
      }
    );
    expect(fetchStub).toHaveBeenNthCalledWith(2, "/api/test-runs/run-1", {
      headers: { "Content-Type": "application/json" }
    });
    expect(fetchStub).toHaveBeenNthCalledWith(
      3,
      "/api/test-projects/project-1/runs",
      { headers: { "Content-Type": "application/json" } }
    );
    expect(fetchStub).toHaveBeenNthCalledWith(
      4,
      "/api/test-runs/run-1/results/result-1",
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ result: "BLOCKED" })
      }
    );
  });

  it("supports result lock and multipart evidence contracts", async () => {
    const evidence = {
      id: "evidence-1",
      original_name: "console.log"
    };
    const fetchStub = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ id: "result-1" }), { status: 200 })
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify([evidence]), { status: 200 })
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify(evidence), { status: 201 })
      )
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchStub);
    const file = new File(["OLT log"], "console.log", { type: "text/plain" });

    await testExecutionApi.lockResult("run-1", "result-1");
    await testExecutionApi.listResultEvidence("result-1");
    await testExecutionApi.uploadResultEvidence(
      "result-1",
      "LOG",
      file,
      "OLT console"
    );
    await testExecutionApi.deleteEvidence("evidence-1");

    expect(fetchStub).toHaveBeenNthCalledWith(
      1,
      "/api/test-runs/run-1/results/result-1/lock",
      { method: "POST", headers: { "Content-Type": "application/json" } }
    );
    const uploadOptions = fetchStub.mock.calls[2][1] as RequestInit;
    expect(fetchStub.mock.calls[2][0]).toBe(
      "/api/run-results/result-1/evidences"
    );
    expect(uploadOptions.method).toBe("POST");
    expect(uploadOptions.headers).toEqual({});
    expect(uploadOptions.body).toBeInstanceOf(FormData);
    expect(testExecutionApi.evidenceDownloadUrl("evidence-1")).toBe(
      "/api/evidences/evidence-1/download"
    );
  });

  it("surfaces API detail errors", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: "Project has run history" }), {
          status: 409,
          headers: { "Content-Type": "application/json" }
        })
      )
    );

    await expect(testExecutionApi.deleteProject("project-1")).rejects.toThrow(
      "Project has run history"
    );
  });
});
