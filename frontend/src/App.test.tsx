import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import App from "./App";
import type { DefectApi } from "./defects/types";
import type { DeviceApi } from "./devices/types";
import type { EnvironmentApi } from "./environments/types";
import type { TestCaseApi } from "./testCases/types";
import type { TestExecutionApi } from "./testExecution/types";


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

const emptyEnvironmentApi: EnvironmentApi = {
  list: async () => [],
  create: async () => {
    throw new Error("not used");
  },
  update: async () => {
    throw new Error("not used");
  },
  delete: async () => undefined
};

const emptyTestExecutionApi: TestExecutionApi = {
  listProjects: async () => [],
  createProject: async () => {
    throw new Error("not used");
  },
  updateProject: async () => {
    throw new Error("not used");
  },
  deleteProject: async () => undefined,
  createRun: async () => {
    throw new Error("not used");
  },
  getRun: async () => {
    throw new Error("not used");
  },
  listRuns: async () => [],
  updateResult: async () => {
    throw new Error("not used");
  },
  lockResult: async () => {
    throw new Error("not used");
  },
  listResultEvidence: async () => [],
  uploadResultEvidence: async () => {
    throw new Error("not used");
  },
  deleteEvidence: async () => undefined,
  evidenceDownloadUrl: (id) => `/api/evidences/${id}/download`
};

const emptyDefectApi: DefectApi = {
  list: async () => [],
  get: async () => {
    throw new Error("not used");
  },
  create: async () => {
    throw new Error("not used");
  },
  update: async () => {
    throw new Error("not used");
  },
  transition: async () => {
    throw new Error("not used");
  },
  listRegressions: async () => [],
  createRegression: async () => {
    throw new Error("not used");
  },
  listEvidence: async () => [],
  uploadEvidence: async () => {
    throw new Error("not used");
  },
  deleteEvidence: async () => undefined,
  evidenceDownloadUrl: (id) => `/api/evidences/${id}/download`
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

  it("opens Test Execution as the third business module", async () => {
    render(
      <App
        api={emptyApi}
        testCaseApi={emptyTestCaseApi}
        testExecutionApi={emptyTestExecutionApi}
        environmentApi={emptyEnvironmentApi}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "测试执行" }));
    expect(
      await screen.findByRole("heading", { name: "测试执行" })
    ).toBeInTheDocument();
  });

  it("opens Defect & Regression as the fourth business module", async () => {
    render(
      <App
        api={emptyApi}
        testCaseApi={emptyTestCaseApi}
        testExecutionApi={emptyTestExecutionApi}
        defectApi={emptyDefectApi}
        environmentApi={emptyEnvironmentApi}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "缺陷闭环" }));
    expect(
      await screen.findByRole("heading", { name: "缺陷闭环" })
    ).toBeInTheDocument();
  });
});
