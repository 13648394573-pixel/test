import type { TestCase, TestCaseApi } from "./types";


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
    throw new Error(body.detail ?? "Test case request failed");
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}


export const testCaseApi: TestCaseApi = {
  list: () => request<TestCase[]>("/api/test-cases"),
  create: (input) =>
    request<TestCase>("/api/test-cases", {
      method: "POST",
      headers: JSON_HEADERS,
      body: JSON.stringify(input)
    }),
  update: (id, input) =>
    request<TestCase>(`/api/test-cases/${id}`, {
      method: "PUT",
      headers: JSON_HEADERS,
      body: JSON.stringify(input)
    }),
  delete: (id) =>
    request<void>(`/api/test-cases/${id}`, {
      method: "DELETE",
      headers: JSON_HEADERS
    })
};
