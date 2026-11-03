const API_BASE = import.meta.env.VITE_API_BASE_URL || "/api";

export class ApiError extends Error {
  constructor(status, errorCode = null, retryAfter = null) {
    const retrySeconds = Number.parseInt(retryAfter, 10);
    const message = status === 429
      ? Number.isFinite(retrySeconds) && retrySeconds > 0
        ? `Çok fazla istek gönderildi. ${retrySeconds} saniye sonra tekrar dene.`
        : "Çok fazla istek gönderildi. Lütfen biraz bekleyip tekrar dene."
      : "İstek tamamlanamadı.";
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.errorCode = errorCode;
    this.retryAfter = Number.isFinite(retrySeconds) && retrySeconds > 0
      ? retrySeconds
      : null;
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
      const retryAfter = response.headers?.get?.("Retry-After") ?? null;
      throw new ApiError(response.status, body?.error_code ?? null, retryAfter);
    }
    return body;
  }

  return { request };
}
