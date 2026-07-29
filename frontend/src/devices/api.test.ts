import { afterEach, describe, expect, it, vi } from "vitest";

import { deviceApi } from "./api";
import type { Device, DeviceInput } from "./types";


const input: DeviceInput = {
  device_type: "ONU",
  vendor: "Huawei",
  model: "HN8546X6",
  serial_number: "ONU-001",
  mac_address: null,
  hardware_version: null,
  software_version: "V5R020"
};

const device: Device = {
  ...input,
  id: "device-1",
  created_at: "2026-07-29T08:00:00",
  updated_at: "2026-07-29T08:00:00"
};


afterEach(() => {
  vi.unstubAllGlobals();
});


describe("deviceApi", () => {
  it("reads the device list from the local API", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify([device]), {
          status: 200,
          headers: { "Content-Type": "application/json" }
        })
      )
    );

    await expect(deviceApi.list()).resolves.toEqual([device]);
    expect(fetch).toHaveBeenCalledWith("/api/devices", {
      headers: { "Content-Type": "application/json" }
    });
  });

  it("sends create, update and delete requests with the correct contract", async () => {
    const fetchStub = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify(device), { status: 201 })
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify(device), { status: 200 })
      )
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchStub);

    await deviceApi.create(input);
    await deviceApi.update("device-1", input);
    await deviceApi.delete("device-1");

    expect(fetchStub).toHaveBeenNthCalledWith(1, "/api/devices", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input)
    });
    expect(fetchStub).toHaveBeenNthCalledWith(2, "/api/devices/device-1", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input)
    });
    expect(fetchStub).toHaveBeenNthCalledWith(3, "/api/devices/device-1", {
      method: "DELETE",
      headers: { "Content-Type": "application/json" }
    });
  });

  it("surfaces the API detail when a request fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({ detail: "Serial number already exists" }),
          { status: 409, headers: { "Content-Type": "application/json" } }
        )
      )
    );

    await expect(deviceApi.create(input)).rejects.toThrow(
      "Serial number already exists"
    );
  });
});
