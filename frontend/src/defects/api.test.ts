import { afterEach, describe, expect, it, vi } from "vitest";

import { defectApi } from "./api";
import type { Defect, DefectInput } from "./types";


const input: DefectInput = {
  source_run_result_id: "result-source",
  title: "WAN does not recover",
  description: "WAN remains disconnected",
  reproduction_steps: "Reconnect the uplink",
  severity: "S2"
};

const defect = {
  id: "defect-1",
  defect_code: "DEF-000001",
  status: "OPEN"
} as Defect;


afterEach(() => {
  vi.unstubAllGlobals();
});


describe("defectApi", () => {
  it("supports defect list, create, detail and update contracts", async () => {
    const fetchStub = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify([defect]), { status: 200 })
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify(defect), { status: 201 })
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify(defect), { status: 200 })
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify(defect), { status: 200 })
      );
    vi.stubGlobal("fetch", fetchStub);

    await defectApi.list();
    await defectApi.create(input);
    await defectApi.get("defect-1");
    await defectApi.update("defect-1", {
      title: input.title,
      description: input.description,
      reproduction_steps: input.reproduction_steps,
      severity: input.severity
    });

    expect(fetchStub).toHaveBeenNthCalledWith(1, "/api/defects", {
      headers: { "Content-Type": "application/json" }
    });
    expect(fetchStub).toHaveBeenNthCalledWith(2, "/api/defects", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input)
    });
    expect(fetchStub).toHaveBeenNthCalledWith(3, "/api/defects/defect-1", {
      headers: { "Content-Type": "application/json" }
    });
    expect(fetchStub).toHaveBeenNthCalledWith(4, "/api/defects/defect-1", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: input.title,
        description: input.description,
        reproduction_steps: input.reproduction_steps,
        severity: input.severity
      })
    });
  });

  it("supports status transition and append-only regression contracts", async () => {
    const regression = { id: "regression-1", result: "PASS" };
    const fetchStub = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify(defect), { status: 200 })
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify([regression]), { status: 200 })
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify(regression), { status: 201 })
      );
    vi.stubGlobal("fetch", fetchStub);

    await defectApi.transition("defect-1", "IN_PROGRESS", null);
    await defectApi.listRegressions("defect-1");
    await defectApi.createRegression("defect-1", {
      verification_run_result_id: "result-pass",
      notes: "Verified"
    });

    expect(fetchStub).toHaveBeenNthCalledWith(
      1,
      "/api/defects/defect-1/status",
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          target_status: "IN_PROGRESS",
          resolution_notes: null
        })
      }
    );
    expect(fetchStub).toHaveBeenNthCalledWith(
      2,
      "/api/defects/defect-1/regressions",
      { headers: { "Content-Type": "application/json" } }
    );
    expect(fetchStub).toHaveBeenNthCalledWith(
      3,
      "/api/defects/defect-1/regressions",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          verification_run_result_id: "result-pass",
          notes: "Verified"
        })
      }
    );
  });

  it("surfaces conflict details", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: "OPEN->RESOLVED" }), {
          status: 409,
          headers: { "Content-Type": "application/json" }
        })
      )
    );

    await expect(
      defectApi.transition("defect-1", "RESOLVED", "Invalid")
    ).rejects.toThrow("OPEN->RESOLVED");
  });
});
