const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8008";

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

export interface ClientResult {
  id: number;
  name: string;
  surname: string;
  middlename: string | null;
  bitrix_id: string | null;
  stage_name: string | null;
}

export interface SearchResponse {
  query: string;
  results: ClientResult[];
}

export interface ClientOut {
  id: number;
  name: string;
  surname: string;
  middlename: string | null;
  bitrix_id: string | null;
  is_blocked: boolean;
}

export interface ContractOut {
  id: number;
  total_amount: string;
  discount: string;
  first_payment: string;
  first_payment_date: string;
  number_of_payments: number;
  preferred_payment_day: number;
}

export interface InstallmentPaymentOut {
  id: number;
  number: number;
  due_date: string;
  amount_due: string;
  status: string;
}

export interface ActualPaymentOut {
  id: number;
  payment_date: string | null;
  amount: string;
}

export interface OtherPaymentOut {
  id: number;
  payment_type: string;
  amount: string;
  comment: string | null;
}

export interface ClientDetailResponse {
  client: ClientOut;
  contract: ContractOut;
  plan_id: number;
  installments: InstallmentPaymentOut[];
  actuals: ActualPaymentOut[];
  other_payments: OtherPaymentOut[];
  total_installments_sum: string;
  total_actuals_sum: string;
  contract_final_amount: string;
  total_tail_amount: string;
  bitrix_deal_url: string | null;
  withdrawals_url: string;
}

export interface WithdrawalRecordOut {
  id: number;
  withdrawal_date: string | null;
  transfer_date: string | null;
  withdrawal_amount: string | null;
  transferred_amount: string | null;
  tail_amount: string;
  comment: string;
}

export interface WithdrawalsPageResponse {
  client: ClientOut;
  records: WithdrawalRecordOut[];
  total_withdrawal_amount: string;
  total_tail_amount: string;
}

export interface WithdrawalMutationResponse {
  success: boolean;
  bitrix_warning: string | null;
}

export interface WithdrawalRecordUpsert {
  withdrawal_date: string | null;
  transfer_date: string | null;
  withdrawal_amount: string | null;
  transferred_amount: string | null;
  comment: string;
}

export const OTHER_PAYMENT_TYPES: { value: string; label: string }[] = [
  { value: "deposit", label: "Судебный депозит" },
  { value: "publication", label: "Публикация" },
  { value: "post", label: "Почтовые расходы" },
  { value: "deposit_extra", label: "Доп. депозит" },
  { value: "publication_extra", label: "Доп. публикация" },
];

export const api = {
  search: (q: string) => request<SearchResponse>(`/api/search?q=${encodeURIComponent(q)}`),

  clientDetail: (clientId: number) => request<ClientDetailResponse>(`/api/clients/${clientId}`),

  updateContract: (
    contractId: number,
    payload: {
      total_amount: string;
      discount: string;
      first_payment: string;
      first_payment_date: string;
      number_of_payments: number;
    },
  ) => request(`/api/contracts/${contractId}`, { method: "PUT", body: JSON.stringify(payload) }),

  createInstallment: (payload: { plan_id: number; due_date: string; amount_due: string }) =>
    request("/api/installments", { method: "POST", body: JSON.stringify(payload) }),
  deleteInstallment: (id: number) => request(`/api/installments/${id}`, { method: "DELETE" }),
  bulkUpdateInstallments: (
    items: { id: number; due_date: string; amount_due: string; status: string }[],
  ) => request("/api/installments/bulk", { method: "PATCH", body: JSON.stringify(items) }),

  createActual: (payload: { plan_id: number; payment_date: string; amount: string }) =>
    request("/api/actuals", { method: "POST", body: JSON.stringify(payload) }),
  deleteActual: (id: number) => request(`/api/actuals/${id}`, { method: "DELETE" }),
  bulkUpdateActuals: (items: { id: number; payment_date: string; amount: string }[]) =>
    request("/api/actuals/bulk", { method: "PATCH", body: JSON.stringify(items) }),

  createOtherPayment: (payload: {
    client_id: number;
    payment_type: string;
    amount: string;
    comment?: string;
  }) => request("/api/other-payments", { method: "POST", body: JSON.stringify(payload) }),
  deleteOtherPayment: (id: number) => request(`/api/other-payments/${id}`, { method: "DELETE" }),
  bulkUpdateOtherPayments: (
    items: { id: number; payment_type: string; amount: string; comment: string | null }[],
  ) => request("/api/other-payments/bulk", { method: "PATCH", body: JSON.stringify(items) }),

  paymentsDashboard: (page: number) => request<PaymentsDashboardResponse>(`/api/payments-dashboard?page=${page}`),

  withdrawalsPage: (clientId: number) =>
    request<WithdrawalsPageResponse>(`/api/clients/${clientId}/withdrawals`),
  createWithdrawal: (clientId: number, payload: WithdrawalRecordUpsert) =>
    request<WithdrawalMutationResponse>(`/api/clients/${clientId}/withdrawals`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateWithdrawal: (recordId: number, payload: WithdrawalRecordUpsert) =>
    request<WithdrawalMutationResponse>(`/api/withdrawals/${recordId}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  deleteWithdrawal: (recordId: number) =>
    request<WithdrawalMutationResponse>(`/api/withdrawals/${recordId}`, { method: "DELETE" }),
};

export interface PaymentsDashboardStats {
  day: string;
  week: string;
  month: string;
  year: string;
}

export interface PaymentsDashboardRow {
  payment_date: string | null;
  amount: string;
  client_name: string | null;
}

export interface PaymentsDashboardResponse {
  stats: PaymentsDashboardStats;
  results: PaymentsDashboardRow[];
  page: number;
  num_pages: number;
}
