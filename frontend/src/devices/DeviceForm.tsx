import { FormEvent, useEffect, useState } from "react";

import type { Device, DeviceInput } from "./types";


interface DeviceFormProps {
  device: Device | null;
  onSubmit: (input: DeviceInput) => Promise<void>;
  onCancel: () => void;
}

interface FormState {
  device_type: string;
  vendor: string;
  model: string;
  serial_number: string;
  mac_address: string;
  hardware_version: string;
  software_version: string;
}

const EMPTY_FORM: FormState = {
  device_type: "",
  vendor: "",
  model: "",
  serial_number: "",
  mac_address: "",
  hardware_version: "",
  software_version: ""
};


function formStateFromDevice(device: Device | null): FormState {
  if (device === null) {
    return EMPTY_FORM;
  }

  return {
    device_type: device.device_type,
    vendor: device.vendor,
    model: device.model,
    serial_number: device.serial_number,
    mac_address: device.mac_address ?? "",
    hardware_version: device.hardware_version ?? "",
    software_version: device.software_version ?? ""
  };
}


export default function DeviceForm({
  device,
  onSubmit,
  onCancel
}: DeviceFormProps) {
  const [form, setForm] = useState<FormState>(() => formStateFromDevice(device));
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setForm(formStateFromDevice(device));
  }, [device]);

  const setField = (field: keyof FormState, value: string) => {
    setForm((current) => ({ ...current, [field]: value }));
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSaving(true);
    try {
      await onSubmit({
        device_type: form.device_type,
        vendor: form.vendor,
        model: form.model,
        serial_number: form.serial_number,
        mac_address: form.mac_address || null,
        hardware_version: form.hardware_version || null,
        software_version: form.software_version || null
      });
    } finally {
      setSaving(false);
    }
  };

  const fields: Array<{
    key: keyof FormState;
    label: string;
    required?: boolean;
  }> = [
    { key: "device_type", label: "设备类型", required: true },
    { key: "vendor", label: "厂商", required: true },
    { key: "model", label: "型号", required: true },
    { key: "serial_number", label: "序列号", required: true },
    { key: "mac_address", label: "MAC 地址" },
    { key: "hardware_version", label: "硬件版本" },
    { key: "software_version", label: "软件版本" }
  ];

  return (
    <form className="device-form" onSubmit={handleSubmit}>
      <div className="form-heading">
        <div>
          <p className="section-kicker">设备档案</p>
          <h3>{device ? "编辑设备" : "新建设备"}</h3>
        </div>
        <button className="button button-quiet" type="button" onClick={onCancel}>
          取消
        </button>
      </div>
      <div className="form-grid">
        {fields.map((field) => (
          <label key={field.key}>
            <span>{field.label}</span>
            <input
              value={form[field.key]}
              required={field.required}
              onChange={(event) => setField(field.key, event.target.value)}
            />
          </label>
        ))}
      </div>
      <div className="form-actions">
        <button className="button button-primary" type="submit" disabled={saving}>
          {saving ? "保存中…" : "保存设备"}
        </button>
      </div>
    </form>
  );
}
