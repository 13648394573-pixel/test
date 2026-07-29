import { useEffect, useState } from "react";

import DeviceForm from "./DeviceForm";
import { deviceApi } from "./api";
import type { Device, DeviceApi, DeviceInput } from "./types";


interface DeviceLibraryPageProps {
  api?: DeviceApi;
}


export default function DeviceLibraryPage({
  api = deviceApi
}: DeviceLibraryPageProps) {
  const [devices, setDevices] = useState<Device[]>([]);
  const [editing, setEditing] = useState<Device | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .list()
      .then(setDevices)
      .catch((reason: Error) => setError(reason.message))
      .finally(() => setLoading(false));
  }, [api]);

  const startCreate = () => {
    setEditing(null);
    setShowForm(true);
    setError("");
  };

  const startEdit = (device: Device) => {
    setEditing(device);
    setShowForm(true);
    setError("");
  };

  const closeForm = () => {
    setEditing(null);
    setShowForm(false);
  };

  const saveDevice = async (input: DeviceInput) => {
    try {
      if (editing) {
        const updated = await api.update(editing.id, input);
        setDevices((current) =>
          current.map((device) => (device.id === updated.id ? updated : device))
        );
      } else {
        const created = await api.create(input);
        setDevices((current) => [created, ...current]);
      }
      closeForm();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "保存设备失败");
    }
  };

  const deleteDevice = async (device: Device) => {
    if (!window.confirm(`确认删除设备 ${device.serial_number}？`)) {
      return;
    }

    try {
      await api.delete(device.id);
      setDevices((current) =>
        current.filter((candidate) => candidate.id !== device.id)
      );
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "删除设备失败");
    }
  };

  return (
    <section className="device-library" aria-labelledby="device-library-title">
      <div className="page-heading">
        <div>
          <p className="section-kicker">Device Library</p>
          <h2 id="device-library-title">设备库</h2>
          <p>集中维护 ONU、OLT 和光猫的基础设备档案。</p>
        </div>
        <button className="button button-primary" type="button" onClick={startCreate}>
          新建设备
        </button>
      </div>

      {error && <p className="error-message" role="alert">{error}</p>}

      {showForm && (
        <DeviceForm device={editing} onSubmit={saveDevice} onCancel={closeForm} />
      )}

      <div className="table-panel">
        {loading ? (
          <p className="empty-state">正在加载设备档案…</p>
        ) : devices.length === 0 ? (
          <p className="empty-state">暂无设备档案</p>
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>类型</th>
                  <th>厂商</th>
                  <th>型号</th>
                  <th>序列号</th>
                  <th>MAC 地址</th>
                  <th>硬件版本</th>
                  <th>软件版本</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {devices.map((device) => (
                  <tr key={device.id}>
                    <td><span className="device-type">{device.device_type}</span></td>
                    <td>{device.vendor}</td>
                    <td>{device.model}</td>
                    <td className="mono">{device.serial_number}</td>
                    <td className="mono">{device.mac_address ?? "—"}</td>
                    <td>{device.hardware_version ?? "—"}</td>
                    <td>{device.software_version ?? "—"}</td>
                    <td>
                      <div className="row-actions">
                        <button
                          className="button button-quiet"
                          type="button"
                          aria-label={`编辑 ${device.serial_number}`}
                          onClick={() => startEdit(device)}
                        >
                          编辑
                        </button>
                        <button
                          className="button button-danger"
                          type="button"
                          aria-label={`删除 ${device.serial_number}`}
                          onClick={() => deleteDevice(device)}
                        >
                          删除
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  );
}
