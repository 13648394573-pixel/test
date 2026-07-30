import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import ResultEditor from "./ResultEditor";
import type { RunResult, TestExecutionApi } from "./types";


const RESULT: RunResult = {
  id: "result-1",
  run_id: "run-1",
  case_source_id: "case-1",
  case_snapshot: {
    case_code: "ONU-WAN-001",
    title: "WAN",
    device_type: "ONU",
    category: "WAN",
    priority: "P1",
    preconditions: null,
    description: null,
    enabled: true,
    steps: []
  },
  snapshot_version: 1,
  result: null,
  integrity_status: "DRAFT",
  actual_result: null,
  blocked_reason: null,
  test_notes: null,
  executed_at: null,
  locked_at: null
};

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});


it("saves detailed draft and locks only after confirmation", async () => {
  const updateResult = vi.fn().mockResolvedValue({
    ...RESULT,
    result: "FAIL",
    actual_result: "No WAN address"
  });
  const lockResult = vi.fn().mockResolvedValue({
    ...RESULT,
    result: "FAIL",
    actual_result: "No WAN address",
    integrity_status: "LOCKED"
  });
  const api = {
    updateResult,
    lockResult,
    listResultEvidence: async () => [],
    evidenceDownloadUrl: (id: string) => `/api/evidences/${id}/download`
  } as unknown as TestExecutionApi;
  vi.spyOn(window, "confirm").mockReturnValue(true);

  render(
    <ResultEditor
      api={api}
      runId="run-1"
      runResult={RESULT}
      onChanged={() => undefined}
    />
  );
  fireEvent.change(screen.getByLabelText("测试结果 ONU-WAN-001"), {
    target: { value: "FAIL" }
  });
  fireEvent.change(screen.getByLabelText("实际结果"), {
    target: { value: "No WAN address" }
  });
  fireEvent.click(screen.getByRole("button", { name: "保存草稿" }));

  await waitFor(() =>
    expect(updateResult).toHaveBeenCalledWith("run-1", "result-1", {
      result: "FAIL",
      actual_result: "No WAN address",
      blocked_reason: null,
      test_notes: null
    })
  );
  fireEvent.click(screen.getByRole("button", { name: "锁定结果" }));
  await waitFor(() =>
    expect(lockResult).toHaveBeenCalledWith("run-1", "result-1")
  );
});


it("renders locked result and evidence as read-only", async () => {
  const api = {
    listResultEvidence: async () => [{
      id: "evidence-1",
      run_result_id: "result-1",
      defect_id: null,
      category: "LOG",
      original_name: "console.log",
      storage_path: "run-results/result-1/file.log",
      media_type: "text/plain",
      file_size: 100,
      sha256: "a".repeat(64),
      description: null,
      created_at: "2026-07-30T10:00:00"
    }],
    evidenceDownloadUrl: (id: string) => `/api/evidences/${id}/download`
  } as unknown as TestExecutionApi;

  render(
    <ResultEditor
      api={api}
      runId="run-1"
      runResult={{ ...RESULT, result: "PASS", integrity_status: "LOCKED" }}
      onChanged={() => undefined}
    />
  );

  expect(await screen.findByText("console.log")).toHaveAttribute(
    "href",
    "/api/evidences/evidence-1/download"
  );
  expect(screen.getByLabelText("测试结果 ONU-WAN-001")).toBeDisabled();
  expect(screen.queryByRole("button", { name: "保存草稿" }))
    .not.toBeInTheDocument();
  expect(screen.queryByLabelText("删除附件 console.log"))
    .not.toBeInTheDocument();
});
