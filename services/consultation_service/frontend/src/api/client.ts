import type { ReportFields, ReportResponse } from "../types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";

async function handle<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail || `Ошибка запроса: ${response.status}`);
  }
  return response.json();
}

export function getReport(dealId: string, token: string): Promise<ReportResponse> {
  const url = `${API_BASE_URL}/api/consultation/${dealId}?token=${encodeURIComponent(token)}`;
  return fetch(url).then((r) => handle<ReportResponse>(r));
}

export function saveReport(dealId: string, token: string, fields: ReportFields): Promise<{ status: string }> {
  const url = `${API_BASE_URL}/api/consultation/${dealId}/save?token=${encodeURIComponent(token)}`;
  return fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ fields }),
  }).then((r) => handle<{ status: string }>(r));
}
