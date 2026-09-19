import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import LabCompatibilityPage from "./LabCompatibilityPage";
import type { LabCompatibilityApi } from "./types";

afterEach(cleanup);

function fakeApi(): LabCompatibilityApi {
  return {
    previewHostKey: vi.fn().mockResolvedValue(
      "SHA256:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    ),
    credentialStatus: vi.fn().mockResolvedValue({ reference: "ref", available: true }),
    enrollCredential: vi.fn().mockResolvedValue({ reference: "ref", available: true }),
    createCheck: vi.fn().mockResolvedValue({
      check_id: "check-1",
      lifecycle: "COMPLETED",
      overall_status: "READY",
      stages: [],
      created_at: "2026-09-19T00:00:00Z",
      updated_at: "2026-09-19T00:00:00Z"
    }),
    getCheck: vi.fn(),
    listEvidence: vi.fn().mockResolvedValue([])
  };
}

describe("LabCompatibilityPage", () => {
  it("states the safety boundary", () => {
    render(<LabCompatibilityPage api={fakeApi()} />);
    expect(screen.getByText(/不会注册 ONU/)).toBeInTheDocument();
    expect(screen.getByText(/不会下发 WAN/)).toBeInTheDocument();
    expect(screen.getByText(/不会修改 OLT 配置/)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "现场兼容性检查" })).toBeInTheDocument();
  });

  it("requires explicit confirmation of the previewed host key", async () => {
    render(<LabCompatibilityPage api={fakeApi()} />);
    fireEvent.change(screen.getByLabelText("OLT 地址"), { target: { value: "192.168.87.204" } });
    fireEvent.change(screen.getByLabelText("ONU Web 地址"), { target: { value: "http://192.168.1.1" } });
    fireEvent.change(screen.getByLabelText("电脑网卡"), { target: { value: "Ethernet" } });
    fireEvent.change(screen.getByLabelText("电脑源地址"), { target: { value: "192.168.1.20" } });
    fireEvent.change(screen.getByLabelText("Ping 目标"), { target: { value: "192.168.1.1" } });
    fireEvent.click(screen.getByRole("button", { name: "读取主机指纹" }));

    await screen.findByText(/SHA256:AAAA/);
    expect(screen.getByRole("button", { name: "开始只读检查" })).toBeDisabled();
    fireEvent.click(screen.getByLabelText("我已核对 OLT 主机指纹"));
    await waitFor(() => expect(screen.getByRole("button", { name: "开始只读检查" })).toBeEnabled());
  });
});
