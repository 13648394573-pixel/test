import type { Device, DeviceApi, DeviceInput } from "./types";


const JSON_HEADERS = { "Content-Type": "application/json" };


async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const response = await fetch(path, {
    headers: JSON_HEADERS,
    ...options
  });

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail ?? "Device request failed");
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}


export const deviceApi: DeviceApi = {
  list: () => request<Device[]>("/api/devices"),
  create: (input) =>
    request<Device>("/api/devices", {
      method: "POST",
      headers: JSON_HEADERS,
      body: JSON.stringify(input)
    }),
  update: (id, input) =>
    request<Device>(`/api/devices/${id}`, {
      method: "PUT",
      headers: JSON_HEADERS,
      body: JSON.stringify(input)
    }),
  delete: (id) =>
    request<void>(`/api/devices/${id}`, {
      method: "DELETE",
      headers: JSON_HEADERS
    })
};
