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

// Çerezle çalışan oturum uç noktaları bu başlığı ister (CSRF koruması).
export const SESSION_HEADERS = { "X-Requested-With": "CareerTracker" };
// Bu isteklerin 401'i "şifre yanlış" veya "oturum yok" demektir; yenileme denenmez.
const NO_REFRESH_PATHS = ["/auth/token", "/auth/register", "/auth/refresh", "/auth/logout"];

export function createApiClient({ onUnauthorized, onTokenRefreshed } = {}) {
  let pendingRefresh = null;

  async function callRefresh() {
    const response = await fetch(`${API_BASE}/auth/refresh`, { method: "POST", headers: SESSION_HEADERS });
    const body = await response.json().catch(() => null);
    if (response.ok && typeof body?.access_token === "string") return { token: body.access_token };
    return { token: null, errorCode: body?.error_code ?? null };
  }

  // httpOnly çerezle yeni erişim token'ı alır; aynı anda gelen çağrılar tek isteği paylaşır.
  function refreshSession() {
    if (!pendingRefresh) {
      pendingRefresh = (async () => {
        try {
          let result = await callRefresh();
          // Başka bir sekme çerezi az önce yeniledi; tarayıcıda artık yenisi var.
          if (!result.token && result.errorCode === "refresh_token_rotated") result = await callRefresh();
          if (result.token) onTokenRefreshed?.(result.token);
          return result.token;
        } catch {
          return null;
        } finally {
          pendingRefresh = null;
        }
      })();
    }
    return pendingRefresh;
  }

  async function perform(path, { token, ...options } = {}, retried = false) {
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
      if (response.status === 401 && token && !retried && !NO_REFRESH_PATHS.some((prefix) => path.startsWith(prefix))) {
        const freshToken = await refreshSession();
        if (freshToken) return perform(path, { ...options, token: freshToken }, true);
      }
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

  async function requestPage(path, { token, limit = 50, offset = 0, newestFirst = false, ...options } = {}) {
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
    // Sunucu varsayılan olarak eskiden yeniye sıralar; listeler en yeniyi ilk sayfada ister.
    if (newestFirst) params.set("order", "newest");
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

  return { request, requestAll, requestPage, refreshSession };
}
