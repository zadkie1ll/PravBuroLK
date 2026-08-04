const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8006";

function getToken(): string | null {
  return localStorage.getItem("access_token");
}

export function setToken(token: string) {
  localStorage.setItem("access_token", token);
}

export function clearToken() {
  localStorage.removeItem("access_token");
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
  return response.json();
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: UserOut;
}

export interface UserOut {
  id: number;
  username: string;
  is_staff: boolean;
  sales_manager_id: number | null;
  sales_manager_name: string;
}

export interface SalesManagerOut {
  id: number;
  name: string;
  email: string;
  phone: string;
  bitrix_user_id: number;
  is_active: boolean;
  megafon_user: string;
  megafon_group: string;
  megafon_clid: string;
}

export interface ManagerStats {
  manager: SalesManagerOut;
  period_start: string;
  period_end: string;
  total_time: string;
  call_count: number;
}

export interface DashboardEntry {
  manager: SalesManagerOut;
  total_time: string;
  call_count: number;
}

export interface DashboardResponse {
  stats: DashboardEntry[];
  period_start: string;
  period_end: string;
}

export interface SalesManagerAdminRow {
  id: number;
  name: string;
  bitrix_user_id: number;
  megafon_user: string;
  megafon_clid: string;
  email: string;
  phone: string;
  user_username: string | null;
  is_active: boolean;
  updated_at: string;
}

export interface SalesManagerListResponse {
  results: SalesManagerAdminRow[];
  count: number;
  page: number;
  per_page: number;
}

export interface LeadSourceAdminRow {
  id: number;
  name: string;
  bitrix_id: number | null;
  is_active: boolean;
  created_at: string;
}

export interface LeadSourceListResponse {
  results: LeadSourceAdminRow[];
  count: number;
  page: number;
  per_page: number;
}

export interface SyncResult {
  ok: boolean;
  total_from_bitrix: number;
  created: number;
  updated: number;
  deactivated: number;
  synced_at: string;
  django_users_created?: number;
  new_credentials?: { username: string; password: string; manager: string }[];
}

export const api = {
  login: (username: string, password: string) =>
    request<TokenResponse>("/auth/login", { method: "POST", body: JSON.stringify({ username, password }) }),
  me: () => request<{ detail: string; user: UserOut }>("/auth/me"),
  myStats: (start?: string, end?: string) => {
    const params = start && end ? `?start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}` : "";
    return request<ManagerStats>(`/stats/me${params}`);
  },
  adminDashboard: (start?: string, end?: string) => {
    const params = start && end ? `?start=${start}&end=${end}` : "";
    return request<DashboardResponse>(`/admin/dashboard${params}`);
  },
  adminManagerDetail: (managerId: number, start?: string, end?: string) => {
    const params = start && end ? `?start=${start}&end=${end}` : "";
    return request<ManagerStats>(`/admin/managers/${managerId}${params}`);
  },
  syncManagers: () => request<SyncResult>("/admin/sync/managers", { method: "POST" }),
  syncSources: () => request<SyncResult>("/admin/sync/sources", { method: "POST" }),
  managersList: (params: { search?: string; is_active?: boolean; page?: number }) => {
    const q = new URLSearchParams();
    if (params.search) q.set("search", params.search);
    if (params.is_active !== undefined) q.set("is_active", String(params.is_active));
    if (params.page) q.set("page", String(params.page));
    return request<SalesManagerListResponse>(`/admin/managers-list?${q.toString()}`);
  },
  patchManagerActive: (id: number, is_active: boolean) =>
    request<SalesManagerAdminRow>(`/admin/managers-list/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ is_active }),
    }),
  sourcesList: (params: { search?: string; is_active?: boolean; page?: number }) => {
    const q = new URLSearchParams();
    if (params.search) q.set("search", params.search);
    if (params.is_active !== undefined) q.set("is_active", String(params.is_active));
    if (params.page) q.set("page", String(params.page));
    return request<LeadSourceListResponse>(`/admin/sources-list?${q.toString()}`);
  },
  patchSourceActive: (id: number, is_active: boolean) =>
    request<LeadSourceAdminRow>(`/admin/sources-list/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ is_active }),
    }),
};
