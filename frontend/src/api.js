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
  async function perform(path, { token, ...options } = {}) {
    const headers = new Headers(options.headers || {});
    if (options.body && !(options.body instanceof URLSearchParams) && !headers.has("Content-Type")) {
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
    return { body, response };
  }

  async function request(path, options = {}) {
    const { body } = await perform(path, options);
    return body;
  }

  async function requestPage(path, { token, limit = 50, offset = 0, ...options } = {}) {
    if (!Number.isInteger(limit) || limit < 1 || limit > 200) {
      throw new RangeError("limit must be between 1 and 200");
    }
    if (!Number.isInteger(offset) || offset < 0) {
      throw new RangeError("offset must be a non-negative integer");
    }

    const [pathname, search = ""] = path.split("?", 2);
    const params = new URLSearchParams(search);
    params.set("limit", String(limit));
    params.set("offset", String(offset));
    const { body, response } = await perform(`${pathname}?${params}`, { ...options, token });
    if (!Array.isArray(body)) throw new TypeError("Expected a paginated list response");

    const headerTotal = Number.parseInt(response.headers?.get?.("X-Total-Count"), 10);
    return {
      items: body,
      totalCount: Number.isFinite(headerTotal) && headerTotal >= 0 ? headerTotal : body.length,
    };
  }

  async function requestAll(path, { token, pageSize = 200, ...options } = {}) {
    if (!Number.isInteger(pageSize) || pageSize < 1 || pageSize > 200) {
      throw new RangeError("pageSize must be between 1 and 200");
    }

    const [pathname, search = ""] = path.split("?", 2);
    const params = new URLSearchParams(search);
    const items = [];
    let offset = 0;

    while (true) {
      params.set("limit", String(pageSize));
      params.set("offset", String(offset));
      const page = await request(`${pathname}?${params}`, { ...options, token });
      if (!Array.isArray(page)) throw new TypeError("Expected a paginated list response");
      items.push(...page);
      if (page.length < pageSize) return items;
      offset += pageSize;
    }
  }

  return { request, requestAll, requestPage };
}
