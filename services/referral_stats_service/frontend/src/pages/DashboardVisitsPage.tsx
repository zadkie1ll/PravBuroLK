import { useEffect, useState } from "react";
import { DashboardStatsResponse, api } from "../api/client";

const ADMIN_PANEL_BASE_URL = import.meta.env.VITE_ADMIN_PANEL_BASE_URL || "http://localhost:5176";

export function DashboardVisitsPage() {
  const [stats, setStats] = useState<DashboardStatsResponse | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.dashboardStats().then(setStats).catch((e) => setError(e instanceof Error ? e.message : "Ошибка запроса"));
  }, []);

  return (
    <div className="flex min-h-screen flex-col bg-gray-100">
      <header className="bg-white p-4 shadow">
        <div className="mx-auto flex max-w-7xl items-center justify-between">
          {/* Заголовок "Статистика" — так же, как в оригинальном dashboard_stats.html
              (там h1 всегда "Статистика", а не "Статистика посещений ЛК" — это только title вкладки) */}
          <h1 className="text-2xl font-bold text-gray-800">Статистика</h1>
          <a
            href={`${ADMIN_PANEL_BASE_URL}/admin`}
            className="rounded-full bg-gradient-to-r from-blue-400 to-blue-600 px-4 py-2 text-sm font-semibold text-white shadow transition hover:from-blue-500 hover:to-blue-700"
          >
            Назад в меню
          </a>
        </div>
      </header>

      <main className="mx-auto w-full max-w-7xl flex-1 p-6">
        <div className="rounded-lg bg-white p-8 shadow">
          <h2 className="mb-6 text-xl font-semibold">Общая статистика по посещениям</h2>

          {error && <p className="mb-4 text-red-600">{error}</p>}

          {stats && (
            <div className="grid grid-cols-2 gap-6 md:grid-cols-4">
              <div className="rounded-xl border border-gray-200 bg-gray-50 p-6 text-center shadow">
                <p className="mb-2 text-gray-500">Сегодня</p>
                <p className="text-3xl font-bold">{stats.today}</p>
              </div>
              <div className="rounded-xl border border-gray-200 bg-gray-50 p-6 text-center shadow">
                <p className="mb-2 text-gray-500">Неделя</p>
                <p className="text-3xl font-bold">{stats.week}</p>
              </div>
              <div className="rounded-xl border border-gray-200 bg-gray-50 p-6 text-center shadow">
                <p className="mb-2 text-gray-500">Месяц</p>
                <p className="text-3xl font-bold">{stats.month}</p>
              </div>
              <div className="rounded-xl border border-gray-200 bg-gray-50 p-6 text-center shadow">
                <p className="mb-2 text-gray-500">Всё время</p>
                <p className="text-3xl font-bold">{stats.all_time}</p>
              </div>
            </div>
          )}
        </div>
      </main>

      <footer className="bg-white p-4 text-center text-sm text-gray-500 shadow">
        © {new Date().getFullYear()} CRM
      </footer>
    </div>
  );
}
