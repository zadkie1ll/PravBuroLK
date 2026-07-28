import { useNavigate } from "react-router-dom";
import { clearToken } from "../api/client";

const LEADREPORT_BASE_URL = import.meta.env.VITE_LEADREPORT_BASE_URL || "http://localhost:5175";
const CLIENT_SEARCH_BASE_URL = import.meta.env.VITE_CLIENT_SEARCH_BASE_URL || "http://localhost:5177";
const REFERRAL_STATS_BASE_URL = import.meta.env.VITE_REFERRAL_STATS_BASE_URL || "http://localhost:5178";
const PAYMENTS_DASHBOARD_BASE_URL = import.meta.env.VITE_CLIENT_SEARCH_BASE_URL || "http://localhost:5177";

export function AdminPanelPage() {
  const navigate = useNavigate();

  function logout() {
    clearToken();
    navigate("/login");
  }

  function openLeadreport() {
    const token = localStorage.getItem("access_token");
    window.location.href = `${LEADREPORT_BASE_URL}/admin?token=${encodeURIComponent(token || "")}`;
  }

  function openClientSearch() {
    const token = localStorage.getItem("access_token");
    window.location.href = `${CLIENT_SEARCH_BASE_URL}/?token=${encodeURIComponent(token || "")}`;
  }

  function openReferralStats() {
    const token = localStorage.getItem("access_token");
    window.location.href = `${REFERRAL_STATS_BASE_URL}/?token=${encodeURIComponent(token || "")}`;
  }

  function openDashboardVisits() {
    const token = localStorage.getItem("access_token");
    window.location.href = `${REFERRAL_STATS_BASE_URL}/visits?token=${encodeURIComponent(token || "")}`;
  }

  function openPaymentsDashboard() {
    const token = localStorage.getItem("access_token");
    window.location.href = `${PAYMENTS_DASHBOARD_BASE_URL}/payments-dashboard?token=${encodeURIComponent(token || "")}`;
  }

  return (
    <div className="flex min-h-screen flex-col bg-gray-100">
      <header className="bg-white p-4 shadow">
        <div className="mx-auto flex max-w-7xl items-center justify-between">
          <h1 className="text-2xl font-bold text-gray-800">Админ-панель</h1>
          <button
            onClick={logout}
            className="rounded-full bg-gradient-to-r from-blue-400 to-blue-600 px-4 py-2 text-sm font-semibold text-white shadow transition hover:from-blue-500 hover:to-blue-700"
          >
            Выйти
          </button>
        </div>
      </header>

      <main className="mx-auto max-w-7xl flex-1 p-6">
        <div className="rounded-lg bg-white p-8 shadow">
          <h2 className="mb-6 text-xl font-semibold">Меню администратора</h2>

          <div className="grid gap-6 md:grid-cols-2">
            <button
              onClick={openClientSearch}
              className="block rounded-xl border border-blue-200 bg-gradient-to-tr from-gray-50 to-blue-100 p-6 text-left shadow transition hover:shadow-lg"
            >
              <h3 className="mb-2 text-lg font-semibold text-gray-800">🔍 Поиск клиентов</h3>
              <p className="text-sm text-gray-600">Ищите клиентов по ФИО, номеру телефона или ID.</p>
            </button>

            <button
              onClick={openReferralStats}
              className="block rounded-xl border border-green-200 bg-gradient-to-tr from-gray-50 to-green-100 p-6 text-left shadow transition hover:shadow-lg"
            >
              <h3 className="mb-2 text-lg font-semibold text-gray-800">📊 Реферальная статистика</h3>
              <p className="text-sm text-gray-600">
                Смотрите количество кликов и заявок по реферальным ссылкам клиентов и сотрудников
              </p>
            </button>

            <button
              onClick={openDashboardVisits}
              className="block rounded-xl border border-blue-300 bg-gradient-to-tr from-gray-50 to-blue-200 p-6 text-left shadow transition hover:shadow-lg"
            >
              <h3 className="mb-2 text-lg font-semibold text-gray-800">📈 Статистика посещений ЛК</h3>
              <p className="text-sm text-gray-600">
                Смотрите количество заходов в личный кабинет по дням, неделям и месяцам.
              </p>
            </button>

            <button
              onClick={openPaymentsDashboard}
              className="block rounded-xl border border-yellow-200 bg-gradient-to-tr from-gray-50 to-yellow-100 p-6 text-left shadow transition hover:shadow-lg"
            >
              <h3 className="mb-2 text-lg font-semibold text-gray-800">💰 Фактические платежи</h3>
              <p className="text-sm text-gray-600">Смотрите статистику и список последних фактических платежей.</p>
            </button>

            <button
              onClick={openLeadreport}
              className="block rounded-xl border border-cyan-200 bg-gradient-to-tr from-slate-50 to-cyan-100 p-6 text-left shadow transition hover:shadow-lg"
            >
              <h3 className="mb-2 text-lg font-semibold text-gray-800">📞 Отчет по менеджерам</h3>
              <p className="text-sm text-gray-600">Смотрите звонки и общее время разговоров по активным менеджерам.</p>
            </button>
          </div>
        </div>
      </main>

      <footer className="bg-white p-4 text-center text-sm text-gray-500 shadow">
        © {new Date().getFullYear()} CRM
      </footer>
    </div>
  );
}
