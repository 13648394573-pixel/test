import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";

import DefectEvidencePanel from "./DefectEvidencePanel";
import type { Defect, DefectApi } from "./types";


const evidence = {
  id: "evidence-1",
  run_result_id: null,
  defect_id: "defect-1",
  category: "SCREENSHOT" as const,
  original_name: "wan.png",
  storage_path: "defects/defect-1/wan.png",
  media_type: "image/png",
  file_size: 20,
  sha256: "a".repeat(64),
  description: null,
  created_at: "2026-07-30T10:00:00"
};
const baseDefect = {
  id: "defect-1",
  status: "RESOLVED"
} as Defect;
const api = {
  listEvidence: async () => [evidence],
  evidenceDownloadUrl: (id: string) => `/api/evidences/${id}/download`
} as unknown as DefectApi;

afterEach(cleanup);


it("allows resolved defects to add evidence but not delete it", async () => {
  render(<DefectEvidencePanel defect={baseDefect} api={api} />);

  expect(await screen.findByText("wan.png")).toBeInTheDocument();
  expect(screen.getByLabelText("选择缺陷附件")).toBeInTheDocument();
  expect(screen.queryByLabelText("删除附件 wan.png")).not.toBeInTheDocument();
});


it("renders closed defect evidence fully read-only", async () => {
  render(
    <DefectEvidencePanel
      defect={{ ...baseDefect, status: "CLOSED" }}
      api={api}
    />
  );

  expect(await screen.findByText("wan.png")).toBeInTheDocument();
  expect(screen.queryByLabelText("选择缺陷附件")).not.toBeInTheDocument();
  expect(screen.getByText("已关闭缺陷附件只读。")).toBeInTheDocument();
});
