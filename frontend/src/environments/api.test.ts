import { afterEach, describe, expect, it, vi } from "vitest";

import { environmentApi } from "./api";


afterEach(() => vi.restoreAllMocks());


describe("environment api", () => {
  it("sends profile CRUD requests to the environment endpoints", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response("[]", { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: "env-1" }), {
        status: 201
      }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: "env-1" }), {
        status: 200
      }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    const input = {
      name: "Lab A",
      description: null,
      enabled: true,
      parameters: []
    };

    await environmentApi.list();
    await environmentApi.create(input);
    await environmentApi.update("env-1", input);
    await environmentApi.delete("env-1");

    expect(fetchMock.mock.calls.map(([path]) => path)).toEqual([
      "/api/environment-profiles",
      "/api/environment-profiles",
      "/api/environment-profiles/env-1",
      "/api/environment-profiles/env-1"
    ]);
    expect(fetchMock.mock.calls[1][1]?.method).toBe("POST");
    expect(fetchMock.mock.calls[2][1]?.method).toBe("PUT");
    expect(fetchMock.mock.calls[3][1]?.method).toBe("DELETE");
  });
});
