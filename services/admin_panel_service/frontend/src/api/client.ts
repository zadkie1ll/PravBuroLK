const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8007";

function getToken(): string | null {
  return localStorage.getItem("access_token");
}

export function setToken(token: string) {
  localStorage.setItem("access_token", token);
}

export function clearToken() {
  localStorage.removeItem("access_token");
}

// Refresh-токен живёт в httponly-куке (недоступен отсюда), поэтому единственный способ
// узнать, что он ещё не протух — реально дёрнуть /auth/refresh и посмотреть на ответ.
let refreshPromise: Promise<string | null> | null = null;

async function refreshAccessToken(): Promise<string | null> {
  if (!refreshPromise) {
    refreshPromise = fetch(`${API_BASE_URL}/auth/refresh`, { method: "POST", credentials: "include" })
      .then((res) => (res.ok ? res.json() : null))
      .then((body: TokenResponse | null) => {
        if (body) setToken(body.access_token);
        return body?.access_token ?? null;
      })
      .catch(() => null)
      .finally(() => {
        refreshPromise = null;
      });
  }
  return refreshPromise;
}

async function request<T>(path: string, options: RequestInit = {}, isRetry = false): Promise<T> {
  const token = getToken();
  const headers: HeadersInit = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(options.headers || {}),
  };

  const response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers, credentials: "include" });

  // access_token протух (или его вовсе нет, но есть живой refresh-token в куке) —
  // тихо перевыпускаем и повторяем запрос один раз, без релогина на глазах у пользователя.
  const isAuthEndpoint = path === "/auth/login" || path === "/auth/refresh" || path.startsWith("/auth/sso-exchange");
  if (response.status === 401 && !isRetry && !isAuthEndpoint) {
    const newToken = await refreshAccessToken();
    if (newToken) return request<T>(path, options, true);
  }

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `Ошибка запроса: ${response.status}`);
  }
  return response.json();
}

export interface UserOut {
  id: number;
  username: string;
  is_staff: boolean;
  role: "admin" | "director" | "marketer";
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: UserOut;
}

export const api = {
  login: (username: string, password: string) =>
    request<TokenResponse>("/auth/login", { method: "POST", body: JSON.stringify({ username, password }) }),
  me: () => request<{ detail: string; user: UserOut }>("/auth/me"),
  logout: () => request<{ detail: string }>("/auth/logout", { method: "POST" }),
  ssoExchange: (token: string) =>
    request<TokenResponse>(`/auth/sso-exchange?token=${encodeURIComponent(token)}`, { method: "POST" }),
};
