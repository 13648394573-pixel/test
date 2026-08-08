import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import DiagnosticPanel from "./DiagnosticPanel";
import type { DiagnosticApi, DiagnosticSession } from "./types";

afterEach(cleanup);


const completed: DiagnosticSession = {
  id: "diag-1",
  run_result_id: "result-1",
  retry_of_session_id: null,
  adapter_key: "huawei-ping",
  adapter_version: "1",
  wan_mode: "IPOE",
  status: "COMPLETED",
  policy_snapshot: {},
  snapshot_version: 1,
  error_code: null,
  error_message: null,
  created_at: "2026-08-08T10:00:00",
  started_at: "2026-08-08T10:00:01",
  completed_at: "2026-08-08T10:00:02",
  attempts: [{
    id: "attempt-1", sequence: 1, layer: "GATEWAY", target: "192.168.1.1",
    attempt_number: 1, status: "PASS", packets_sent: 3, packets_received: 3,
    loss_percent: "0", latency_min_ms: "1", latency_avg_ms: "2",
    latency_max_ms: "3", raw_output: "ok", error_code: null,
    started_at: "2026-08-08T10:00:01", finished_at: "2026-08-08T10:00:02",
    evidence_links: [{ evidence_id: "evidence-1" }]
  }]
};


it("starts a Huawei ping diagnostic and renders layered evidence", async () => {
  const api: DiagnosticApi = {
    list: vi.fn().mockResolvedValue([]),
    create: vi.fn().mockResolvedValue(completed),
    get: vi.fn().mockResolvedValue(completed)
  };
  render(<DiagnosticPanel resultId="result-1" locked={false} api={api} />);
  await waitFor(() => expect(api.list).toHaveBeenCalledWith("result-1"));

  fireEvent.click(screen.getByRole("button", { name: "开始Ping诊断" }));

  await waitFor(() => expect(api.create).toHaveBeenCalled());
  expect(await screen.findByText("GATEWAY")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "诊断证据" })).toHaveAttribute(
    "href", "/api/evidences/evidence-1/download"
  );
});


it("does not allow starting diagnostics for a locked result", async () => {
  const api: DiagnosticApi = {
    list: vi.fn().mockResolvedValue([]),
    create: vi.fn(),
    get: vi.fn()
  };
  render(<DiagnosticPanel resultId="result-1" locked api={api} />);
  expect(screen.getByRole("button", { name: "开始Ping诊断" })).toBeDisabled();
});
