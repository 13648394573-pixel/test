import DeviceLibraryPage from "./devices/DeviceLibraryPage";
import { deviceApi } from "./devices/api";
import type { DeviceApi } from "./devices/types";


interface AppProps {
  api?: DeviceApi;
}


function App({ api = deviceApi }: AppProps) {
  return (
    <div className="application">
      <header className="app-header">
        <div>
          <p className="eyebrow">网络设备测试工作台</p>
          <h1>Test Workbench</h1>
        </div>
        <span className="local-badge">本地工作区</span>
      </header>
      <main>
        <DeviceLibraryPage api={api} />
      </main>
    </div>
  );
}

export default App;
