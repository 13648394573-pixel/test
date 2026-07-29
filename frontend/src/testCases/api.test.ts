import { afterEach, describe, expect, it, vi } from "vitest";

import { testCaseApi } from "./api";
import type { TestCase, TestCaseInput } from "./types";


const input: TestCaseInput = {
  case_code: "ONU-WAN-001",
  title: "Verify IPoE WAN",
  device_type: "ONU",
  category: "WAN",
  priority: "P1",
  preconditions: "ONU is registered",
  description: null,
  enabled: true,
  steps: [
    {
      action: "Create an IPoE WAN",
      expected_result: "WAN obtains an address"
    }
  ]
};

const testCase: TestCase = {
  ...input,
  id: "case-1",
  created_at: "2026-07-29T08:00:00",
  updated_at: "2026-07-29T08:00:00",
  steps: [
    {
      ...input.steps[0],
      id: "step-1",
      test_case_id: "case-1",
      step_number: 1,
      created_at: "2026-07-29T08:00:00",
      updated_at: "2026-07-29T08:00:00"
    }
  ]
};


afterEach(() => {
  vi.unstubAllGlobals();
});


describe("testCaseApi", () => {
  it("reads the test case list from the local API", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify([testCase]), {
          status: 200,
          headers: { "Content-Type": "application/json" }
        })
      )
    );

    await expect(testCaseApi.list()).resolves.toEqual([testCase]);
    expect(fetch).toHaveBeenCalledWith("/api/test-cases", {
      headers: { "Content-Type": "application/json" }
    });
  });

  it("sends aggregate create, update and delete requests", async () => {
    const fetchStub = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify(testCase), { status: 201 })
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify(testCase), { status: 200 })
      )
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchStub);

    await testCaseApi.create(input);
    await testCaseApi.update("case-1", input);
    await testCaseApi.delete("case-1");

    expect(fetchStub).toHaveBeenNthCalledWith(1, "/api/test-cases", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input)
    });
    expect(fetchStub).toHaveBeenNthCalledWith(
      2,
      "/api/test-cases/case-1",
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(input)
      }
    );
    expect(fetchStub).toHaveBeenNthCalledWith(
      3,
      "/api/test-cases/case-1",
      {
        method: "DELETE",
        headers: { "Content-Type": "application/json" }
      }
    );
  });

  it("surfaces the API detail when a request fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({ detail: "Case code already exists" }),
          { status: 409, headers: { "Content-Type": "application/json" } }
        )
      )
    );

    await expect(testCaseApi.create(input)).rejects.toThrow(
      "Case code already exists"
    );
  });
});
