import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import BatchEvidencePanel from "./BatchEvidencePanel";
import type { RunResult } from "../testExecution/types";


afterEach(cleanup);


const result = (id: string, locked = false): RunResult => ({
  id,
  run_id: "run-1",
  case_source_id: id,
  case_snapshot: { case_code: id, title: id, device_type: "ONU", category: "WAN", priority: "P1", preconditions: null, description: null, enabled: true, steps: [] },
  snapshot_version: 1,
  result: null,
  integrity_status: locked ? "LOCKED" : "DRAFT",
  actual_result: null,
  blocked_reason: null,
  test_notes: null,
  executed_at: null,
  locked_at: null
});


test("uploads multiple files to selected draft results", async () => {
  const upload = vi.fn().mockResolvedValue([]);
  const changed = vi.fn();
  render(
    <BatchEvidencePanel
      results={[result("CASE-1"), result("CASE-2"), result("CASE-3", true)]}
      upload={upload}
      onUploaded={changed}
    />
  );

  fireEvent.click(screen.getByLabelText("关联 CASE-1"));
  fireEvent.click(screen.getByLabelText("关联 CASE-2"));
  fireEvent.change(screen.getByLabelText("批量附件文件"), {
    target: { files: [new File(["a"], "a.log"), new File(["b"], "b.log")] }
  });
  fireEvent.click(screen.getByRole("button", { name: "批量上传" }));

  await waitFor(() => expect(upload).toHaveBeenCalledOnce());
  expect(upload.mock.calls[0][0]).toEqual(["CASE-1", "CASE-2"]);
  expect(upload.mock.calls[0][1]).toHaveLength(2);
  expect(changed).toHaveBeenCalledOnce();
  expect(screen.getByLabelText("关联 CASE-3")).toBeDisabled();
});


test("clears selections and files when the active run changes", () => {
  const upload = vi.fn().mockResolvedValue([]);
  const view = render(
    <BatchEvidencePanel
      results={[result("CASE-1"), result("CASE-2")]}
      upload={upload}
      onUploaded={() => undefined}
    />
  );
  fireEvent.click(view.getByLabelText("关联 CASE-1"));
  fireEvent.change(view.getByLabelText("批量附件文件"), {
    target: { files: [new File(["a"], "a.log")] }
  });
  expect(view.getByText("1 个结果 · 1 个文件")).toBeInTheDocument();

  const nextResults = [
    { ...result("CASE-3"), run_id: "run-2" },
    { ...result("CASE-4"), run_id: "run-2" }
  ];
  view.rerender(
    <BatchEvidencePanel
      results={nextResults}
      upload={upload}
      onUploaded={() => undefined}
    />
  );

  expect(view.getByText("0 个结果 · 0 个文件")).toBeInTheDocument();
  expect(view.getByLabelText("关联 CASE-3")).not.toBeChecked();
});
