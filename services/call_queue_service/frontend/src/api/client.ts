const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8001";

function getToken(): string | null {
  return localStorage.getItem("access_token");
}

function getRefreshToken(): string | null {
  return localStorage.getItem("refresh_token");
}

export function setTokens(accessToken: string, refreshToken: string) {
  localStorage.setItem("access_token", accessToken);
  localStorage.setItem("refresh_token", refreshToken);
}

export function clearToken() {
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
}

// Несколько запросов могут словить 401 одновременно (например, параллельный поллинг) —
// держим один и тот же promise рефреша, чтобы не выпускать кучу refresh-токенов разом.
let refreshInFlight: Promise<string> | null = null;

async function refreshAccessToken(): Promise<string> {
  if (!refreshInFlight) {
    refreshInFlight = (async () => {
      const refreshToken = getRefreshToken();
      if (!refreshToken) throw new Error("no refresh token");
      const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });
      if (!response.ok) {
        clearToken();
        throw new Error("refresh failed");
      }
      const data: TokenResponse = await response.json();
      setTokens(data.access_token, data.refresh_token);
      return data.access_token;
    })().finally(() => {
      refreshInFlight = null;
    });
  }
  return refreshInFlight;
}

async function request<T>(path: string, options: RequestInit = {}, isRetry = false): Promise<T> {
  const token = getToken();
  const headers: HeadersInit = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(options.headers || {}),
  };

  const response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers });
  if (response.status === 401 && !isRetry && getRefreshToken() && path !== "/auth/refresh") {
    try {
      await refreshAccessToken();
    } catch {
      window.location.href = "/login";
      throw new Error("Сессия истекла, нужен повторный вход");
    }
    return request<T>(path, options, true);
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `Ошибка запроса: ${response.status}`);
  }
  return response.json();
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface Choice {
  value: string;
  label: string;
}

export interface QueueItem {
  entity_type: string;
  entity_id: number;
  deal_id: number | null;
  lead_id: number | null;
  contact_id: number | null;
  client_name: string;
  phone: string;
  raw_phone: string;
  bitrix_url: string;
  comments: string;
  stage_id: string;
  created_at: string;
  phone_insights: {
    region_label: string;
    timezone_label: string;
    local_time: string;
    is_estimated: boolean;
  };
  status: string;
  manual_decision: string;
  call_id: string;
  source?: string;
  whatsapp_followup_url: string;
  whatsapp_followup_web_url: string;
  whatsapp_desktop_url: string;
  telegram_desktop_url: string;
  max_desktop_url: string;
  max_followup_url: string;
}

export interface QueueState {
  queue: QueueItem[];
  queue_size: number;
  current_index: number;
  current_item: QueueItem | null;
  manager_name: string;
  entity_type: string;
  auto_dial_enabled: boolean;
  stage_choices: Choice[];
  category_choices: Choice[];
}

export interface CallTimelineEntry {
  created_at: string;
  title: string;
  title_human: string;
  cmd: string;
  type: string;
  status: string;
  direction: string;
}

export interface CallSnapshot {
  call_id: string;
  marker: { state: string; label: string };
  manager_answered: boolean;
  latest_history_status: string;
  last_event_type: string;
  last_event_direction: string;
  phone_result: { state: string; label: string };
  requires_manager_confirmation: boolean;
  timeline: CallTimelineEntry[];
}

export interface CallSnapshotResponse {
  ok: boolean;
  snapshot: CallSnapshot;
  item: QueueItem;
}

export interface ResolveCallResponse {
  ok: boolean;
  decision: string;
  bitrix_url: string;
  item: QueueItem;
}

export interface AutoNextResponse {
  ok: boolean;
  started: boolean;
  call_id: string;
  no_next: boolean;
  hold_for_manager: boolean;
  await_manager_decision: boolean;
  already_processed: boolean;
}

export const api = {
  login: (email: string, password: string) =>
    request<TokenResponse>("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }),
  register: (email: string, password: string) =>
    request<TokenResponse>("/auth/register", { method: "POST", body: JSON.stringify({ email, password }) }),
  getQueueState: () => request<QueueState>("/queue"),
  buildQueue: (payload: Record<string, unknown>) =>
    request<QueueState>("/queue/build", { method: "POST", body: JSON.stringify(payload) }),
  addCustomItem: (payload: Record<string, unknown>) =>
    request<QueueState>("/queue/add-custom", { method: "POST", body: JSON.stringify(payload) }),
  resetQueue: () => request<QueueState>("/queue/reset", { method: "POST" }),
  removeItem: (index: number) => request<QueueState>(`/queue/remove/${index}`, { method: "POST" }),
  startCall: () => request<QueueState>("/queue/start-call", { method: "POST" }),
  getMegafonStatus: (callid: string) => request<CallSnapshotResponse>(`/queue/megafon/status?callid=${encodeURIComponent(callid)}`),
  resolveMegafonCall: (callid: string, decision: string) =>
    request<ResolveCallResponse>("/queue/megafon/resolve", { method: "POST", body: JSON.stringify({ callid, decision }) }),
  triggerAutoNext: (completedCallid: string, forceResume = false) =>
    request<AutoNextResponse>("/queue/megafon/auto-next", {
      method: "POST",
      body: JSON.stringify({ completed_callid: completedCallid, force_resume: forceResume }),
    }),
};
