import { useState } from "react";

import DeviceLibraryPage from "./devices/DeviceLibraryPage";
import { deviceApi } from "./devices/api";
import type { DeviceApi } from "./devices/types";
import TestCaseLibraryPage from "./testCases/TestCaseLibraryPage";
import { testCaseApi as defaultTestCaseApi } from "./testCases/api";
import type { TestCaseApi } from "./testCases/types";


interface AppProps {
  api?: DeviceApi;
  testCaseApi?: TestCaseApi;
}


function App({
  api = deviceApi,
  testCaseApi = defaultTestCaseApi
}: AppProps) {
  const [activeModule, setActiveModule] = useState<"devices" | "test-cases">(
    "devices"
  );

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
      </nav>
      <main>
        {activeModule === "devices" ? (
          <DeviceLibraryPage api={api} />
        ) : (
          <TestCaseLibraryPage api={testCaseApi} />
        )}
      </main>
    </div>
  );
}

export default App;
