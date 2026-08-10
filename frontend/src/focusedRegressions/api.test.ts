import { afterEach, describe, expect, it, vi } from "vitest";

import { focusedRegressionApi } from "./api";
import type { FocusedRegressionRun } from "./types";


const focused = {
  id: "focused-1",
  test_run_id: "run-focused-1",
  defect_id: "defect-1"
} as FocusedRegressionRun;


afterEach(() => vi.unstubAllGlobals());


describe("focusedRegressionApi", () => {
  it("supports create, defect history and run detail contracts", async () => {
    const fetchStub = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify(focused), { status: 201 })
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify([focused]), { status: 200 })
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify(focused), { status: 200 })
      );
    vi.stubGlobal("fetch", fetchStub);

    const input = {
      device_source_id: "device-1",
      environment_profile_id: "environment-1",
      source_run_result_id: "result-source"
    };
    await focusedRegressionApi.create("defect-1", input);
    await focusedRegressionApi.listForDefect("defect-1");
    await focusedRegressionApi.getByRun("run-focused-1");

    expect(fetchStub).toHaveBeenNthCalledWith(
      1,
      "/api/defects/defect-1/focused-regression-runs",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(input)
      }
    );
    expect(fetchStub).toHaveBeenNthCalledWith(
      2,
      "/api/defects/defect-1/focused-regression-runs",
      { headers: { "Content-Type": "application/json" } }
    );
    expect(fetchStub).toHaveBeenNthCalledWith(
      3,
      "/api/focused-regression-runs/run-focused-1",
      { headers: { "Content-Type": "application/json" } }
    );
  });
});
