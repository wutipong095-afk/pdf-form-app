/** Typed fetch helpers for the Flask backend */

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export async function apiJson<T>(url: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(url, opts);
  if (res.status === 401) {
    location.href = "/login";
    throw new ApiError("unauthorized", 401);
  }
  const data = (await res.json().catch(() => ({}))) as T & { error?: string };
  if (!res.ok) {
    throw new ApiError(data.error || `HTTP ${res.status}`, res.status);
  }
  return data;
}

/** Like the old api() — returns Response for callers that parse JSON themselves */
export async function api(url: string, opts?: RequestInit): Promise<Response> {
  const res = await fetch(url, opts);
  if (res.status === 401) {
    location.href = "/login";
    throw new ApiError("unauthorized", 401);
  }
  return res;
}
