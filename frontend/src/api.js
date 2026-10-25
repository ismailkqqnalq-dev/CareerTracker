const API_BASE = import.meta.env.VITE_API_BASE_URL || "/api";

export class ApiError extends Error {
  constructor(status, errorCode = null) {
    super("İstek tamamlanamadı.");
    this.name = "ApiError";
    this.status = status;
    this.errorCode = errorCode;
  }
}

export function createApiClient({ onUnauthorized } = {}) {
  async function request(path, { token, ...options } = {}) {
    const headers = new Headers(options.headers || {});
    if (options.body && !(options.body instanceof URLSearchParams)) {
      headers.set("Content-Type", "application/json");
    }
    if (token) headers.set("Authorization", `Bearer ${token}`);

    const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
    const body = response.status === 204
      ? null
      : await response.json().catch(() => null);

    if (!response.ok) {
      if (response.status === 401) onUnauthorized?.();
      throw new ApiError(response.status, body?.error_code ?? null);
    }
    return body;
  }

  return { request };
}
