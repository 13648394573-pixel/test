import { afterEach, describe, expect, it, vi } from "vitest";

import { reportApi } from "./api";


afterEach(() => vi.restoreAllMocks());


describe("report api", () => {
  it("uses report and archive lifecycle endpoints", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response("[]", { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: "report-1" }), {
        status: 201
      }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: "archive-1" }), {
        status: 201
      }));

    await reportApi.listProjectReports("project-1");
    await reportApi.generateReport("run-1", "Acceptance");
    await reportApi.createArchive("report-1");

    expect(fetchMock.mock.calls[0][0]).toBe(
      "/api/test-projects/project-1/reports"
    );
    expect(fetchMock.mock.calls[1]).toEqual([
      "/api/test-runs/run-1/reports",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ title: "Acceptance" })
      })
    ]);
    expect(fetchMock.mock.calls[2][0]).toBe(
      "/api/reports/report-1/archive"
    );
    expect(reportApi.reportDownloadUrl("report-1")).toBe(
      "/api/reports/report-1/download"
    );
    expect(reportApi.archiveDownloadUrl("archive-1")).toBe(
      "/api/archives/archive-1/download"
    );
  });
});
