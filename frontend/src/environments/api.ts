import type {
  EnvironmentApi,
  EnvironmentProfile,
  EnvironmentProfileInput
} from "./types";


const JSON_HEADERS = { "Content-Type": "application/json" };


async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(path, { headers: JSON_HEADERS, ...options });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail ?? "Environment request failed");
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}


export const environmentApi: EnvironmentApi = {
  list: () => request<EnvironmentProfile[]>("/api/environment-profiles"),
  create: (input: EnvironmentProfileInput) =>
    request<EnvironmentProfile>("/api/environment-profiles", {
      method: "POST",
      body: JSON.stringify(input)
    }),
  update: (id: string, input: EnvironmentProfileInput) =>
    request<EnvironmentProfile>(`/api/environment-profiles/${id}`, {
      method: "PUT",
      body: JSON.stringify(input)
    }),
  delete: (id: string) =>
    request<void>(`/api/environment-profiles/${id}`, { method: "DELETE" })
};
