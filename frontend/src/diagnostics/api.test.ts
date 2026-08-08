import { afterEach, expect, it, vi } from "vitest";

import { diagnosticApi } from "./api";


afterEach(() => vi.unstubAllGlobals());


it("creates and lists diagnostics through the v1 api", async () => {
  const session = { id: "diag-1", status: "PENDING", attempts: [] };
  const fetchStub = vi.fn()
    .mockResolvedValueOnce(new Response(JSON.stringify(session), { status: 202 }))
    .mockResolvedValueOnce(new Response(JSON.stringify([session]), { status: 200 }));
  vi.stubGlobal("fetch", fetchStub);

  const input = {
    wan_mode: "IPOE" as const,
    gateway_target: "192.168.1.1",
    public_ip_target: "1.1.1.1",
    domain_target: "example.com",
    packet_count: 3,
    timeout_seconds: 5,
    max_attempts_per_layer: 2
  };
  await diagnosticApi.create("result-1", input);
  await diagnosticApi.list("result-1");

  expect(fetchStub).toHaveBeenNthCalledWith(
    1,
    "/api/run-results/result-1/diagnostics",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input)
    }
  );
  expect(fetchStub).toHaveBeenNthCalledWith(
    2,
    "/api/run-results/result-1/diagnostics",
    { headers: { "Content-Type": "application/json" } }
  );
});
