import { useState } from "react";

import DefectPage from "./defects/DefectPage";
import { defectApi as defaultDefectApi } from "./defects/api";
import type { DefectApi } from "./defects/types";
import DeviceLibraryPage from "./devices/DeviceLibraryPage";
import { deviceApi } from "./devices/api";
import type { DeviceApi } from "./devices/types";
import EnvironmentProfilePage from "./environments/EnvironmentProfilePage";
import { environmentApi as defaultEnvironmentApi } from "./environments/api";
import type { EnvironmentApi } from "./environments/types";
import TestCaseLibraryPage from "./testCases/TestCaseLibraryPage";
import { testCaseApi as defaultTestCaseApi } from "./testCases/api";
import type { TestCaseApi } from "./testCases/types";
import TestExecutionPage from "./testExecution/TestExecutionPage";
import { testExecutionApi as defaultTestExecutionApi } from "./testExecution/api";
import type { TestExecutionApi } from "./testExecution/types";


interface AppProps {
  api?: DeviceApi;
  testCaseApi?: TestCaseApi;
  testExecutionApi?: TestExecutionApi;
  defectApi?: DefectApi;
  environmentApi?: EnvironmentApi;
}


function App({
  api = deviceApi,
  testCaseApi = defaultTestCaseApi,
  testExecutionApi = defaultTestExecutionApi,
  defectApi = defaultDefectApi,
  environmentApi = defaultEnvironmentApi
}: AppProps) {
  const [activeModule, setActiveModule] = useState<
    "devices" | "test-cases" | "test-execution" | "defects" | "environments"
  >("devices");

  return (
    <div className="application">
      <header className="app-header">
        <div>
          <p className="eyebrow">网络设备测试工作台</p>
          <h1>Test Workbench</h1>
        </div>
        <span className="local-badge">本地工作区</span>
      </header>
      <nav className="module-nav" aria-label="业务模块">
        <button
          type="button"
          className={activeModule === "devices" ? "active" : ""}
          onClick={() => setActiveModule("devices")}
        >
          设备库
        </button>
        <button
          type="button"
          className={activeModule === "test-cases" ? "active" : ""}
          onClick={() => setActiveModule("test-cases")}
        >
          测试用例库
        </button>
        <button
          type="button"
          className={activeModule === "test-execution" ? "active" : ""}
          onClick={() => setActiveModule("test-execution")}
        >
          测试执行
        </button>
        <button
          type="button"
          className={activeModule === "defects" ? "active" : ""}
          onClick={() => setActiveModule("defects")}
        >
          缺陷闭环
        </button>
        <button
          type="button"
          className={activeModule === "environments" ? "active" : ""}
          onClick={() => setActiveModule("environments")}
        >
          环境模板
        </button>
      </nav>
      <main>
        {activeModule === "devices" ? (
          <DeviceLibraryPage api={api} />
        ) : activeModule === "test-cases" ? (
          <TestCaseLibraryPage api={testCaseApi} />
        ) : activeModule === "test-execution" ? (
          <TestExecutionPage
            api={testExecutionApi}
            deviceApi={api}
            testCaseApi={testCaseApi}
            environmentApi={environmentApi}
          />
        ) : activeModule === "defects" ? (
          <DefectPage api={defectApi} executionApi={testExecutionApi} />
        ) : (
          <EnvironmentProfilePage api={environmentApi} />
        )}
      </main>
    </div>
  );
}

export default App;
