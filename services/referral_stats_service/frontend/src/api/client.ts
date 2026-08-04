const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8009";

function getToken(): string | null {
  return localStorage.getItem("access_token");
}

export function setToken(token: string) {
  localStorage.setItem("access_token", token);
}

async function request<T>(path: string): Promise<T> {
  const token = getToken();
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `Ошибка запроса: ${response.status}`);
  }
  return response.json();
}

export interface ReferralStatRow {
  type: string;
  name: string;
  ref_link: string;
  clicks: number;
  applications: number;
}

export interface ReferralStatsResponse {
  results: ReferralStatRow[];
  count: number;
  page: number;
  per_page: number;
}

export interface DashboardStatsResponse {
  today: number;
  week: number;
  month: number;
  all_time: number;
}

export const api = {
  dashboardStats: () => request<DashboardStatsResponse>("/api/dashboard-stats"),

  referralStats: (params: { filter: string; sort: string; page: number; per_page: number }) => {
    const q = new URLSearchParams({
      filter: params.filter,
      sort: params.sort,
      page: String(params.page),
      per_page: String(params.per_page),
    });
    return request<ReferralStatsResponse>(`/api/referral-stats?${q.toString()}`);
  },
};
