const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8011";

function getToken(): string | null {
  return localStorage.getItem("access_token");
}

export function setToken(token: string) {
  localStorage.setItem("access_token", token);
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: HeadersInit = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(options.headers || {}),
  };

  const response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `Ошибка запроса: ${response.status}`);
  }
  if (response.status === 204) return undefined as T;
  return response.json();
}

export interface SourceStat {
  source: string;
  clicks: number;
}

export interface DestinationStat {
  destination: string;
  sources: SourceStat[];
  total_clicks: number;
}

export interface StatsResponse {
  stats: DestinationStat[];
}

export interface MutationResponse {
  success: boolean;
  message: string;
}

export const api = {
  stats: () => request<StatsResponse>("/api/stats"),

  createSource: (payload: { source: string; destination: string }) =>
    request<MutationResponse>("/api/sources", { method: "POST", body: JSON.stringify(payload) }),

  updateSource: (source: string, payload: { new_source: string; new_destination: string }) =>
    request<MutationResponse>(`/api/sources/${encodeURIComponent(source)}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),

  deleteSource: (source: string) =>
    request<MutationResponse>(`/api/sources/${encodeURIComponent(source)}`, { method: "DELETE" }),

  updateDestination: (payload: { old_destination: string; new_destination: string }) =>
    request<MutationResponse>("/api/destinations", { method: "PUT", body: JSON.stringify(payload) }),

  deleteDestination: (destination: string) =>
    request<MutationResponse>("/api/destinations", {
      method: "DELETE",
      body: JSON.stringify({ destination }),
    }),
};
