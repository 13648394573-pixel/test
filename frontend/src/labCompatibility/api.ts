import type {
  CompatibilityCheck,
  CompatibilityCheckInput,
  CompatibilityEvidence,
  CredentialAvailability,
  LabCompatibilityApi
} from "./types";

const JSON_HEADERS = { "Content-Type": "application/json" };

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(path, { headers: JSON_HEADERS, ...options });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail ?? "现场检查请求失败");
  }
  return response.json() as Promise<T>;
}

export const labCompatibilityApi: LabCompatibilityApi = {
  async previewHostKey(host, port) {
    const result = await request<{ fingerprint: string }>(
      "/api/lab-compatibility-checks/host-key-preview",
      {
        method: "POST",
        body: JSON.stringify({ olt_host: host, olt_port: port })
      }
    );
    return result.fingerprint;
  },
  credentialStatus: (reference) =>
    request<CredentialAvailability>(
      `/api/local-credentials/${encodeURIComponent(reference)}/status`
    ),
  enrollCredential: (reference, secret) =>
    request<CredentialAvailability>(
      `/api/local-credentials/${encodeURIComponent(reference)}`,
      { method: "PUT", body: JSON.stringify({ secret }) }
    ),
  createCheck: (input: CompatibilityCheckInput) =>
    request<CompatibilityCheck>("/api/lab-compatibility-checks", {
      method: "POST",
      body: JSON.stringify(input)
    }),
  getCheck: (checkId) =>
    request<CompatibilityCheck>(`/api/lab-compatibility-checks/${checkId}`),
  listEvidence: (checkId) =>
    request<CompatibilityEvidence[]>(
      `/api/lab-compatibility-checks/${checkId}/evidence`
    )
};
