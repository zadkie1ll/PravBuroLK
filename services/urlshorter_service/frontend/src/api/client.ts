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

// --- Новая система разметки ---

export interface DictionaryItem {
  id: number;
  code: string;
  is_active: boolean;
}

export interface BotBlockItem {
  id: number;
  key: string;
  title: string;
  is_active: boolean;
}

export interface DictionariesResponse {
  utm_sources: DictionaryItem[];
  utm_mediums: DictionaryItem[];
  bot_blocks: BotBlockItem[];
}

export interface MarketingLinkOut {
  id: number;
  source: string;
  link_type: string;
  destination: string;
  utm_source: string;
  utm_medium: string;
  utm_campaign: string;
  utm_content: string;
  utm_term: string;
  bot_block: string | null;
  public_link: string;
}

export interface CreateMarketingLinkResponse {
  link: MarketingLinkOut;
  is_existing: boolean;
}

export interface CreateMarketingLinkPayload {
  link_type: "site" | "bot" | "other";
  destination?: string;
  utm_source_id: number;
  utm_medium_id: number;
  utm_campaign: string;
  utm_content?: string;
  utm_term?: string;
  bot_block_id?: number;
}

export interface MarketingStatsRow {
  group_value: string;
  clicks: number;
}

export interface MarketingStatsResponse {
  rows: MarketingStatsRow[];
  total_clicks: number;
  page: number;
  total_pages: number;
  total_rows: number;
}

export interface KnownValuesResponse {
  campaigns: string[];
  contents: string[];
  terms: string[];
}

export interface MarketingStatsFilters {
  group_by?: string;
  page?: number;
  page_size?: number;
  click_from?: string;
  click_to?: string;
  created_from?: string;
  created_to?: string;
  utm_source?: string;
  utm_medium?: string;
  utm_campaign?: string;
  utm_content?: string;
  utm_term?: string;
  link_type?: string;
  destination?: string;
}

function toQueryString(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") search.set(key, String(value));
  }
  const s = search.toString();
  return s ? `?${s}` : "";
}

export const marketingApi = {
  dictionaries: (allValues = false) =>
    request<DictionariesResponse>(`/api/marketing/dictionaries${toQueryString({ all_values: allValues ? "true" : "" })}`),

  knownValues: () => request<KnownValuesResponse>("/api/marketing/known-values"),

  addUtmSource: (code: string) =>
    request<DictionaryItem>("/api/marketing/dictionaries/utm-sources", { method: "POST", body: JSON.stringify({ code }) }),
  toggleUtmSource: (id: number) =>
    request<DictionaryItem>(`/api/marketing/dictionaries/utm-sources/${id}/toggle`, { method: "PATCH" }),

  addUtmMedium: (code: string) =>
    request<DictionaryItem>("/api/marketing/dictionaries/utm-mediums", { method: "POST", body: JSON.stringify({ code }) }),
  toggleUtmMedium: (id: number) =>
    request<DictionaryItem>(`/api/marketing/dictionaries/utm-mediums/${id}/toggle`, { method: "PATCH" }),

  addBotBlock: (key: string, title: string) =>
    request<BotBlockItem>("/api/marketing/dictionaries/bot-blocks", { method: "POST", body: JSON.stringify({ key, title }) }),
  toggleBotBlock: (id: number) =>
    request<BotBlockItem>(`/api/marketing/dictionaries/bot-blocks/${id}/toggle`, { method: "PATCH" }),

  createLink: (payload: CreateMarketingLinkPayload) =>
    request<CreateMarketingLinkResponse>("/api/marketing/links", { method: "POST", body: JSON.stringify(payload) }),

  stats: (filters: MarketingStatsFilters) =>
    request<MarketingStatsResponse>(`/api/marketing/stats${toQueryString(filters as Record<string, string | number | undefined>)}`),

  async downloadStatsCsv(filters: MarketingStatsFilters) {
    const token = getToken();
    const qs = toQueryString(filters as Record<string, string | number | undefined>);
    const response = await fetch(`${API_BASE_URL}/api/marketing/stats/export.csv${qs}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!response.ok) throw new Error(`Ошибка экспорта: ${response.status}`);
    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "marketing_stats.csv";
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
  },
};

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
