import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import App from "./App";
import type { DeviceApi } from "./devices/types";
import type { TestCaseApi } from "./testCases/types";


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

const emptyTestCaseApi: TestCaseApi = {
  list: async () => [],
  create: async () => {
    throw new Error("not used");
  },
  update: async () => {
    throw new Error("not used");
  },
  delete: async () => undefined
};

afterEach(cleanup);


describe("application", () => {
  it("opens the Device Library as the first business module", async () => {
    render(<App api={emptyApi} testCaseApi={emptyTestCaseApi} />);

    expect(
      screen.getByRole("heading", { name: "Test Workbench" })
    ).toBeInTheDocument();
    expect(
      await screen.findByRole("heading", { name: "设备库" })
    ).toBeInTheDocument();
  });

  it("switches to the Test Case Library without losing Device access", async () => {
    render(<App api={emptyApi} testCaseApi={emptyTestCaseApi} />);

    fireEvent.click(screen.getByRole("button", { name: "测试用例库" }));
    expect(
      await screen.findByRole("heading", { name: "测试用例库" })
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "设备库" }));
    expect(
      await screen.findByRole("heading", { name: "设备库" })
    ).toBeInTheDocument();
  });
});
