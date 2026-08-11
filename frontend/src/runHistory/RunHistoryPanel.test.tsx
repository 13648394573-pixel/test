import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import RunHistoryPanel from "./RunHistoryPanel";
import type { RunHistoryApi, RunHistoryItem } from "./types";


afterEach(cleanup);


const ITEMS: RunHistoryItem[] = [
  {
    id: "run-1",
    run_no: "RUN-000001",
    project_id: "project-1",
    project_name: "Release",
    project_version: "R1",
    device: { device_type: "ONU", vendor: "Huawei", model: "X1", serial_number: "ONU-1", software_version: "V1" },
    status: "COMPLETED",
    summary: { total: 1, pass: 1, fail: 0, blocked: 0, unset: 0 },
    started_at: "2026-08-11T09:00:00",
    finished_at: "2026-08-11T10:00:00"
  },
  {
    id: "run-2",
    run_no: "RUN-000002",
    project_id: "project-1",
    project_name: "Release",
    project_version: "R2",
    device: { device_type: "ONU", vendor: "Huawei", model: "X1", serial_number: "ONU-1", software_version: "V2" },
    status: "COMPLETED",
    summary: { total: 1, pass: 0, fail: 1, blocked: 0, unset: 0 },
    started_at: "2026-08-11T11:00:00",
    finished_at: "2026-08-11T12:00:00"
  }
];


test("filters history and compares two selected runs", async () => {
  const api: RunHistoryApi = {
    search: async () => ({ items: ITEMS, total: 2, limit: 25, offset: 0 }),
    compare: async () => ({
      runs: ITEMS,
      rows: [{
        case_code: "WAN-001",
        title: "WAN",
        base: { run_id: "run-1", result: "PASS", evidence_count: 0 },
        targets: [{ run_id: "run-2", result: "FAIL", evidence_count: 1, change: "REGRESSED" }]
      }]
    })
  };
  render(<RunHistoryPanel api={api} projectId="project-1" onOpen={() => undefined} />);

  expect(await screen.findByText("RUN-000001")).toBeInTheDocument();
  fireEvent.click(screen.getByLabelText("选择 RUN-000001"));
  fireEvent.click(screen.getByLabelText("选择 RUN-000002"));
  fireEvent.click(screen.getByRole("button", { name: "比较所选 Run" }));

  await waitFor(() => expect(screen.getByText(/REGRESSED/)).toBeInTheDocument());
  expect(screen.getByText("WAN-001")).toBeInTheDocument();
});


test("submits complete filters and pages through history", async () => {
  const search = vi.fn().mockImplementation(async (filters) => ({
    items: filters.offset === 25 ? [ITEMS[1]] : [ITEMS[0]],
    total: 30,
    limit: 25,
    offset: filters.offset ?? 0
  }));
  const api: RunHistoryApi = {
    search,
    compare: async () => ({ runs: [], rows: [] })
  };
  render(<RunHistoryPanel api={api} projectId="project-1" onOpen={() => undefined} />);
  await screen.findByText("RUN-000001");

  fireEvent.change(screen.getByLabelText("项目版本"), { target: { value: "R1" } });
  fireEvent.change(screen.getByLabelText("设备类型"), { target: { value: "ONU" } });
  fireEvent.change(screen.getByLabelText("设备厂商"), { target: { value: "Huawei" } });
  fireEvent.change(screen.getByLabelText("设备型号"), { target: { value: "X1" } });
  fireEvent.change(screen.getByLabelText("开始时间起"), { target: { value: "2026-08-01T09:00" } });
  fireEvent.change(screen.getByLabelText("开始时间止"), { target: { value: "2026-08-11T18:00" } });
  fireEvent.click(screen.getByRole("button", { name: "筛选" }));

  await waitFor(() => expect(search).toHaveBeenLastCalledWith(expect.objectContaining({
    project_id: "project-1",
    project_version: "R1",
    device_type: "ONU",
    vendor: "Huawei",
    model: "X1",
    started_from: "2026-08-01T09:00",
    started_to: "2026-08-11T18:00",
    offset: 0
  })));
  expect(screen.getByText("共 30 条")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "下一页" }));

  await waitFor(() => expect(search).toHaveBeenLastCalledWith(expect.objectContaining({ offset: 25 })));
  expect(await screen.findByText("RUN-000002")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "上一页" })).toBeEnabled();
});
