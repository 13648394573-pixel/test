import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import DeviceLibraryPage from "./DeviceLibraryPage";
import type { Device, DeviceApi, DeviceInput } from "./types";


const DEVICE: Device = {
  id: "device-1",
  device_type: "ONU",
  vendor: "Huawei",
  model: "HN8546X6",
  serial_number: "ONU-001",
  mac_address: "00:11:22:33:44:55",
  hardware_version: "V1",
  software_version: "V5R020",
  created_at: "2026-07-29T08:00:00",
  updated_at: "2026-07-29T08:00:00"
};


class MemoryDeviceApi implements DeviceApi {
  private devices: Device[];

  constructor(devices: Device[] = []) {
    this.devices = [...devices];
  }

  async list(): Promise<Device[]> {
    return [...this.devices];
  }

  async create(input: DeviceInput): Promise<Device> {
    const device: Device = {
      ...input,
      id: `device-${this.devices.length + 1}`,
      created_at: "2026-07-29T09:00:00",
      updated_at: "2026-07-29T09:00:00"
    };
    this.devices.push(device);
    return device;
  }

  async update(id: string, input: DeviceInput): Promise<Device> {
    const index = this.devices.findIndex((device) => device.id === id);
    const updated = {
      ...this.devices[index],
      ...input,
      updated_at: "2026-07-29T10:00:00"
    };
    this.devices[index] = updated;
    return updated;
  }

  async delete(id: string): Promise<void> {
    this.devices = this.devices.filter((device) => device.id !== id);
  }
}


afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});


describe("Device Library", () => {
  it("shows existing devices", async () => {
    render(<DeviceLibraryPage api={new MemoryDeviceApi([DEVICE])} />);

    const row = await screen.findByRole("row", { name: /ONU-001/ });

    expect(within(row).getByText("Huawei")).toBeInTheDocument();
    expect(within(row).getByText("HN8546X6")).toBeInTheDocument();
    expect(within(row).getByText("V5R020")).toBeInTheDocument();
  });

  it("creates a device from the new-device form", async () => {
    render(<DeviceLibraryPage api={new MemoryDeviceApi()} />);

    fireEvent.click(screen.getByRole("button", { name: "新建设备" }));
    fireEvent.change(screen.getByLabelText("设备类型"), {
      target: { value: "OLT" }
    });
    fireEvent.change(screen.getByLabelText("厂商"), {
      target: { value: "ZTE" }
    });
    fireEvent.change(screen.getByLabelText("型号"), {
      target: { value: "C600" }
    });
    fireEvent.change(screen.getByLabelText("序列号"), {
      target: { value: "OLT-001" }
    });
    fireEvent.click(screen.getByRole("button", { name: "保存设备" }));

    expect(
      await screen.findByRole("row", { name: /OLT-001/ })
    ).toHaveTextContent("ZTE");
  });

  it("edits an existing device", async () => {
    render(<DeviceLibraryPage api={new MemoryDeviceApi([DEVICE])} />);
    await screen.findByRole("row", { name: /ONU-001/ });

    fireEvent.click(screen.getByRole("button", { name: "编辑 ONU-001" }));
    fireEvent.change(screen.getByLabelText("软件版本"), {
      target: { value: "V5R021" }
    });
    fireEvent.click(screen.getByRole("button", { name: "保存设备" }));

    await waitFor(() => {
      expect(
        screen.getByRole("row", { name: /ONU-001/ })
      ).toHaveTextContent("V5R021");
    });
  });

  it("deletes a device after confirmation", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    render(<DeviceLibraryPage api={new MemoryDeviceApi([DEVICE])} />);
    await screen.findByRole("row", { name: /ONU-001/ });

    fireEvent.click(screen.getByRole("button", { name: "删除 ONU-001" }));

    await waitFor(() => {
      expect(
        screen.queryByRole("row", { name: /ONU-001/ })
      ).not.toBeInTheDocument();
    });
    expect(screen.getByText("暂无设备档案")).toBeInTheDocument();
  });
});
