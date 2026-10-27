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

export async function request<T>(path: string, options: RequestInit = {}, isRetry = false): Promise<T> {
  const token = getToken();
  const headers: HeadersInit = {
    ...(options.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
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

/** XHR exposes upload progress; FormData is streamed by the browser, not encoded in JS. */
export async function uploadRequest<T>(path: string, method: string, body: FormData,
  onProgress?: (percent: number) => void, isRetry = false): Promise<T> {
  const response = await new Promise<{ status: number; text: string }>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open(method, `${API_BASE_URL}${path}`);
    xhr.withCredentials = true;
    xhr.timeout = 3600000;
    const token = getToken();
    if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress?.(Math.round(event.loaded / event.total * 100));
    };
    xhr.onload = () => resolve({ status: xhr.status, text: xhr.responseText });
    xhr.onerror = () => reject(new Error("Загрузка прервана. Проверьте соединение и лимит размера файла на сервере."));
    xhr.ontimeout = () => reject(new Error("Время загрузки истекло. Проверьте соединение и попробуйте снова."));
    xhr.onabort = () => reject(new Error("Загрузка отменена"));
    onProgress?.(0);
    xhr.send(body);
  });
  if (response.status === 401 && !isRetry) {
    const token = await refreshAccessToken();
    if (token) return uploadRequest<T>(path, method, body, onProgress, true);
  }
  if (response.status === 413) throw new Error("Файл превышает разрешённый сервером размер загрузки");
  let data;
  try { data = JSON.parse(response.text); } catch { data = {}; }
  if (response.status < 200 || response.status >= 300) {
    throw new Error(data.detail || `Ошибка загрузки: ${response.status}`);
  }
  return data as T;
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
