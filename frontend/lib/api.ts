import { API_URL } from "./types";

export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, detail: unknown) {
    super(typeof detail === "string" ? detail : JSON.stringify(detail));
    this.status = status;
    this.detail = detail;
  }

  get message(): string {
    if (typeof this.detail === "string") return this.detail;
    if (Array.isArray(this.detail)) {
      return this.detail.map((d) => (d as { msg?: string }).msg ?? String(d)).join("; ");
    }
    return super.message;
  }
}

function token(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem("lmt.token");
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("Content-Type", "application/json");
  const jwt = token();
  if (jwt) headers.set("Authorization", `Bearer ${jwt}`);

  const response = await fetch(`${API_URL}${path}`, { ...options, headers });
  if (response.status === 204) return undefined as T;

  let body: unknown = null;
  try {
    body = await response.json();
  } catch {
    body = null;
  }
  if (!response.ok) {
    throw new ApiError(response.status, (body as { detail?: unknown })?.detail ?? body ?? response.statusText);
  }
  return body as T;
}

export const get = <T,>(path: string) => api<T>(path);
export const post = <T,>(path: string, body?: unknown) =>
  api<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });
export const patch = <T,>(path: string, body: unknown) =>
  api<T>(path, { method: "PATCH", body: JSON.stringify(body) });
