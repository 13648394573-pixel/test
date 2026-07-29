export interface DeviceInput {
  device_type: string;
  vendor: string;
  model: string;
  serial_number: string;
  mac_address: string | null;
  hardware_version: string | null;
  software_version: string | null;
}

export interface Device extends DeviceInput {
  id: string;
  created_at: string;
  updated_at: string;
}

export interface DeviceApi {
  list(): Promise<Device[]>;
  create(input: DeviceInput): Promise<Device>;
  update(id: string, input: DeviceInput): Promise<Device>;
  delete(id: string): Promise<void>;
}
