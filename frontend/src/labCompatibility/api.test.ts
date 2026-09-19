import { afterEach, describe, expect, it, vi } from "vitest";

import { labCompatibilityApi } from "./api";
import type { CompatibilityCheckInput } from "./types";

const input: CompatibilityCheckInput = {
  olt_host: "10.0.0.2",
  olt_port: 22,
  expected_host_key_fingerprint: "SHA256:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
  olt_username_ref: "olt.lab.username",
  olt_password_ref: "olt.lab.password",
  onu_serial_number: null,
  frame: null,
  slot: null,
  pon_port: null,
  ont_id: null,
  onu_web_url: "http://192.168.1.1",
  onu_web_username_ref: "onu.lab.username",
  onu_web_password_ref: "onu.lab.password",
  onu_adapter_key: "neutral-v1",
  pc_interface_name: "Ethernet",
  pc_source_address: "192.168.1.20",
  pc_ping_target: "192.168.1.1"
};

afterEach(() => vi.unstubAllGlobals());

describe("labCompatibilityApi", () => {
  it("sends only credential references when creating a check", async () => {
    const response = {
      check_id: "check-1",
      lifecycle: "PENDING",
      overall_status: null,
      stages: [],
      created_at: "2026-09-19T00:00:00Z",
      updated_at: "2026-09-19T00:00:00Z"
    };
    const fetchStub = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(response), { status: 202 })
    );
    vi.stubGlobal("fetch", fetchStub);

    await labCompatibilityApi.createCheck(input);

    const body = JSON.parse(String(fetchStub.mock.calls[0][1]?.body));
    expect(body.olt_password_ref).toBe("olt.lab.password");
    expect(JSON.stringify(body)).not.toContain("secret-value");
    expect(fetchStub).toHaveBeenCalledWith("/api/lab-compatibility-checks", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input)
    });
  });

  it("encodes credential references before enrollment", async () => {
    const fetchStub = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ reference: "onu lab/user", available: true }), {
        status: 200
      })
    );
    vi.stubGlobal("fetch", fetchStub);

    await labCompatibilityApi.enrollCredential("onu lab/user", "secret-value");

    expect(fetchStub).toHaveBeenCalledWith(
      "/api/local-credentials/onu%20lab%2Fuser",
      expect.objectContaining({ method: "PUT" })
    );
  });
});
