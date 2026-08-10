import { useEffect, useMemo, useState } from "react";

import type { Defect } from "../defects/types";
import { deviceApi as defaultDeviceApi } from "../devices/api";
import type { Device, DeviceApi } from "../devices/types";
import { environmentApi as defaultEnvironmentApi } from "../environments/api";
import type {
  EnvironmentApi,
  EnvironmentProfile
} from "../environments/types";
import ResultEditor from "../testExecution/ResultEditor";
import { testExecutionApi as defaultExecutionApi } from "../testExecution/api";
import type { TestExecutionApi } from "../testExecution/types";
import { focusedRegressionApi as defaultFocusedApi } from "./api";
import type {
  FocusedRegressionApi,
  FocusedRegressionRun
} from "./types";


interface FocusedRegressionPanelProps {
  defect: Defect;
  api?: FocusedRegressionApi;
  deviceApi?: DeviceApi;
  environmentApi?: EnvironmentApi;
  executionApi?: TestExecutionApi;
}

export default function FocusedRegressionPanel({
  defect,
  api = defaultFocusedApi,
  deviceApi = defaultDeviceApi,
  environmentApi = defaultEnvironmentApi,
  executionApi = defaultExecutionApi
}: FocusedRegressionPanelProps) {
  const [items, setItems] = useState<FocusedRegressionRun[]>([]);
  const [devices, setDevices] = useState<Device[]>([]);
  const [environments, setEnvironments] = useState<EnvironmentProfile[]>([]);
  const [deviceId, setDeviceId] = useState("");
  const [environmentId, setEnvironmentId] = useState("");
  const [sourceResultId, setSourceResultId] = useState(
    defect.source_run_result_id
  );
  const [active, setActive] = useState<FocusedRegressionRun | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    setSourceResultId(defect.source_run_result_id);
    setActive(null);
    Promise.all([
      api.listForDefect(defect.id),
      deviceApi.list(),
      environmentApi.list()
    ])
      .then(([history, deviceItems, profileItems]) => {
        setItems(history);
        setDevices(deviceItems);
        setEnvironments(profileItems.filter((profile) => profile.enabled));
      })
      .catch((reason: Error) => setError(reason.message))
      .finally(() => setLoading(false));
  }, [api, defect.id, defect.source_run_result_id, deviceApi, environmentApi]);

  const sourceOptions = useMemo(() => [
    defect.source_run_result,
    ...defect.regressions
      .filter((regression) =>
        regression.result === "FAIL" || regression.result === "BLOCKED"
      )
      .map((regression) => regression.verification_run_result)
  ], [defect]);

  const createRun = async () => {
    if (!deviceId || !environmentId || !sourceResultId) return;
    try {
      setError("");
      const created = await api.create(defect.id, {
        device_source_id: deviceId,
        environment_profile_id: environmentId,
        source_run_result_id: sourceResultId
      });
      setItems((current) => [created, ...current]);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "创建精简回归失败");
    }
  };

  const openRun = async (runId: string) => {
    try {
      setError("");
      setActive(await api.getByRun(runId));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "加载精简回归失败");
    }
  };

  const refreshActive = async () => {
    if (!active) return;
    const refreshed = await api.getByRun(active.test_run_id);
    setActive(refreshed);
    setItems((current) => current.map((item) =>
      item.id === refreshed.id ? refreshed : item
    ));
  };

  return (
    <section className="focused-regression-panel" aria-label="精简回归">
      <div className="focused-regression-heading">
        <div>
          <h3>精简回归</h3>
          <p>从失败证据创建只包含目标用例的新 TestRun。</p>
        </div>
      </div>

      {defect.status === "RESOLVED" && (
        <div className="focused-regression-launcher">
          <label>
            回归来源
            <select
              value={sourceResultId}
              onChange={(event) => setSourceResultId(event.target.value)}
            >
              {sourceOptions.map((result) => (
                <option key={result.id} value={result.id}>
                  {result.case_snapshot.case_code} · {result.result}
                </option>
              ))}
            </select>
          </label>
          <label>
            执行设备
            <select
              value={deviceId}
              onChange={(event) => setDeviceId(event.target.value)}
            >
              <option value="">请选择设备</option>
              {devices.map((device) => (
                <option key={device.id} value={device.id}>
                  {device.vendor} {device.model} · {device.serial_number}
                </option>
              ))}
            </select>
          </label>
          <label>
            环境模板
            <select
              value={environmentId}
              onChange={(event) => setEnvironmentId(event.target.value)}
            >
              <option value="">请选择启用模板</option>
              {environments.map((profile) => (
                <option key={profile.id} value={profile.id}>
                  {profile.name}
                </option>
              ))}
            </select>
          </label>
          <button
            className="button button-primary"
            type="button"
            disabled={!deviceId || !environmentId || !sourceResultId}
            onClick={createRun}
          >
            创建精简回归
          </button>
        </div>
      )}

      {loading ? (
        <p>正在加载回归历史…</p>
      ) : items.length === 0 ? (
        <p>暂无精简回归 Run</p>
      ) : (
        <div className="focused-regression-history">
          {items.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => openRun(item.test_run_id)}
              aria-label={`查看精简回归 ${item.test_run_id}`}
            >
              <span className="mono">{item.test_run_id}</span>
              <span>{item.test_run.results[0].case_snapshot.case_code}</span>
              <strong>
                {item.test_run.status === "COMPLETED" ? "已完成" : "执行中"}
              </strong>
            </button>
          ))}
        </div>
      )}

      {active && (
        <article className="focused-regression-detail">
          <h4>{active.test_run.results[0].case_snapshot.title}</h4>
          <p className="mono">{active.test_run_id}</p>
          <ResultEditor
            api={executionApi}
            runId={active.test_run_id}
            runResult={active.test_run.results[0]}
            onChanged={() => { void refreshActive(); }}
          />
        </article>
      )}
      {error && <p className="error-message" role="alert">{error}</p>}
    </section>
  );
}
