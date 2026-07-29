import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import App from "./App";
import type { DeviceApi } from "./devices/types";


const emptyApi: DeviceApi = {
  list: async () => [],
  create: async () => {
    throw new Error("not used");
  },
  update: async () => {
    throw new Error("not used");
  },
  delete: async () => undefined
};


describe("application", () => {
  it("opens the Device Library as the first business module", async () => {
    render(<App api={emptyApi} />);

    expect(
      screen.getByRole("heading", { name: "Test Workbench" })
    ).toBeInTheDocument();
    expect(
      await screen.findByRole("heading", { name: "设备库" })
    ).toBeInTheDocument();
  });
});
