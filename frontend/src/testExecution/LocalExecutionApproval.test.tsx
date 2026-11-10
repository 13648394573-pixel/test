import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import LocalExecutionApproval from "./LocalExecutionApproval";

const operation = (id: number) => ({
  operation_id: `delete-${id}`, session_id: "session-1", kind: "DELETE", port_id: id,
  serial_number: "AABBCCDDEEFF0011", line_profile_id: 10, service_profile_id: 10,
  consumers: [id === 53 ? "IPOE" : "PPPOE"], baseline_hash: "b".repeat(64), read_hash: "d".repeat(64),
  creation_event_id: `created-${id}`,
  mapping: { olt_binding_hash: "c".repeat(64), fsp: "0/2/9", ont_id: 12, vlan: id === 53 ? 1000 : 2000,
    gemport: 1, user_vlan: id === 53 ? 1000 : 2000, candidate_id: id,
    tag_transform: "translate", business_type: "multi-service" }
});
const view = {
  session_id: "session-1", test_run_id: "run-1", run_result_id: "result-1",
  status: "WAITING_OPERATOR", integrity_status: "DRAFT", runner_configured: true,
  pending_interaction: { id: "approval-1", instructions: "核对完整范围", options: ["CONFIRM", "CANCEL"],
    preview_hash: "a".repeat(64), action_code: "cleanup_service_ports", target: {}, affected_service_ports: [53, 54],
    service_port_preview: { operations: [operation(53), operation(54)], evidence_ids: ["proof-1"], retained_consumers: [] } }
};
async function load() {
  render(<LocalExecutionApproval />);
  fireEvent.change(screen.getByRole("textbox", { name: "本地执行会话 ID" }), { target: { value: "session-1" } });
  fireEvent.click(screen.getByRole("button", { name: "读取执行会话" }));
  await screen.findByText("当前状态：WAITING_OPERATOR");
}
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

it("previews cleanup separately and only deletes on explicit checked execution", async () => {
  const posts: { path: string; body: string | undefined }[] = [];
  const preview = { operations: [operation(53), operation(54)], evidence_ids: ["proof-1"], retained_consumers: [], preview_hash: "e".repeat(64) };
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, options) => {
    const path = String(input);
    if (options?.method === "POST") posts.push({ path, body: options.body as string });
    return new Response(JSON.stringify({ ...view, cleanup_available: true,
      cleanup_preview: path.endsWith("cleanup-preview") ? preview : null,
      status: path.endsWith("cleanup-execute") ? "RECOVERY_REQUIRED" : "WAITING_OPERATOR",
      cleanup_outcome: path.endsWith("cleanup-execute") ? { status: "PASS", items: [{ port_id: 53, status: "DELETED" }, { port_id: 54, status: "DELETED" }] } : null }));
  });
  await load();
  fireEvent.click(screen.getByRole("button", { name: "预览本次端口清理（只读查询）" }));
  const region = await screen.findByRole("region", { name: "本次端口清理预览" });
  expect(within(region).getByText("created-53")).toBeInTheDocument();
  expect(within(region).getByText("created-54")).toBeInTheDocument();
  const execute = screen.getByRole("button", { name: "确认执行本次端口清理" });
  expect(execute).toBeDisabled();
  expect(posts).toEqual([{ path: "/api/skill-executions/session-1/cleanup-preview", body: "{}" }]);
  fireEvent.click(screen.getByRole("checkbox", { name: "我确认删除上述本会话创建端口，且不代表恢复 WAN" }));
  fireEvent.click(execute);
  await screen.findByText("当前状态：RECOVERY_REQUIRED");
  expect(posts[1]).toEqual({ path: "/api/skill-executions/session-1/cleanup-execute",
    body: JSON.stringify({ approved: true, preview_hash: "e".repeat(64) }) });
  expect(screen.getByText("清理完成不代表 WAN 恢复；请人工核对，不会自动继续测试。" )).toBeInTheDocument();
});

it("refuses port approval when the typed impact preview is missing", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ ...view,
    pending_interaction: { ...view.pending_interaction, service_port_preview: null } })));
  await load();
  expect(screen.getByText("完整端口预览缺失，禁止审批。请重新读取。" )).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "确认审批" })).toBeDisabled();
});

it("shows every deletion and creation provenance and clears stale approval on conflict", async () => {
  const requests: string[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    requests.push(String(input));
    return String(input).endsWith("respond") ? new Response("{}", { status: 409 }) : new Response(JSON.stringify(view));
  });
  await load();
  const impact = screen.getByRole("region", { name: "端口影响预览" });
  expect(within(impact).getAllByText("DELETE")).toHaveLength(2);
  expect(within(impact).getByText("created-53")).toBeInTheDocument();
  expect(within(impact).getByText("created-54")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("checkbox", { name: "我已核对目标和完整影响范围" }));
  const confirm = screen.getByRole("button", { name: "确认审批" });
  fireEvent.click(confirm); fireEvent.click(confirm);
  expect(await screen.findByRole("alert")).toHaveTextContent("409");
  expect(screen.queryByRole("button", { name: "确认审批" })).not.toBeInTheDocument();
  expect(requests.filter((p) => p.endsWith("respond"))).toHaveLength(1);
});

it.each([{ integrity_status: "LOCKED" }, { runner_configured: false }])("keeps protected executions read-only (%j)", async (extra) => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ ...view, ...extra })));
  await load();
  expect(screen.getByRole("checkbox", { name: "我已核对目标和完整影响范围" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "确认审批" })).toBeDisabled();
});

it("never advances from reading or approval; a separate explicit confirmation is required", async () => {
  const posts: string[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, options) => {
    if (options?.method === "POST") posts.push(String(input));
    return new Response(JSON.stringify({ ...view, status: "RUNNING", pending_interaction: null }));
  });
  const consent = vi.spyOn(window, "confirm").mockReturnValue(false);
  render(<LocalExecutionApproval />);
  fireEvent.change(screen.getByRole("textbox", { name: "本地执行会话 ID" }), { target: { value: "session-1" } });
  fireEvent.click(screen.getByRole("button", { name: "读取执行会话" }));
  const advance = await screen.findByRole("button", { name: "推进一步（可能操作设备）" });
  expect(posts).toEqual([]);
  fireEvent.click(advance);
  expect(posts).toEqual([]);
  consent.mockReturnValue(true);
  fireEvent.click(advance);
  await screen.findByText("当前状态：RUNNING");
  expect(posts).toEqual(["/api/skill-executions/session-1/advance"]);
});
