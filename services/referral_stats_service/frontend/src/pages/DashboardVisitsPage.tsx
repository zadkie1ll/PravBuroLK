import { useEffect, useState } from "react";
import { DashboardStatsResponse, api } from "../api/client";

export function DashboardVisitsPage() {
  const [stats, setStats] = useState<DashboardStatsResponse | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.dashboardStats().then(setStats).catch((e) => setError(e instanceof Error ? e.message : "Ошибка запроса"));
  }, []);

  return (
    <div className="flex min-h-screen flex-col bg-[#f7f7f8] text-[#1c1c1e]">
      <header className="border-b border-gray-200 bg-white">
        <div className="mx-auto max-w-6xl px-6 py-4">
          {/* Заголовок "Статистика" — так же, как в оригинальном dashboard_stats.html
              (там h1 всегда "Статистика", а не "Статистика посещений ЛК" — это только title вкладки) */}
          <h1 className="text-base font-semibold">Статистика</h1>
        </div>
      </header>

      <main className="mx-auto w-full max-w-6xl flex-1 px-6 py-6">
        <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
          <h2 className="mb-6 text-lg font-semibold">Общая статистика по посещениям</h2>

          {error && <p className="mb-4 text-sm text-red-600">{error}</p>}

          {stats && (
            <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
              <div className="rounded-xl border border-gray-200 bg-[#f7f7f8] p-5 text-center">
                <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-gray-500">Сегодня</p>
                <p className="text-2xl font-semibold text-[#1c1c1e]">{stats.today}</p>
              </div>
              <div className="rounded-xl border border-gray-200 bg-[#f7f7f8] p-5 text-center">
                <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-gray-500">Неделя</p>
                <p className="text-2xl font-semibold text-[#1c1c1e]">{stats.week}</p>
              </div>
              <div className="rounded-xl border border-gray-200 bg-[#f7f7f8] p-5 text-center">
                <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-gray-500">Месяц</p>
                <p className="text-2xl font-semibold text-[#1c1c1e]">{stats.month}</p>
              </div>
              <div className="rounded-xl border border-gray-200 bg-[#f7f7f8] p-5 text-center">
                <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-gray-500">Всё время</p>
                <p className="text-2xl font-semibold text-[#1c1c1e]">{stats.all_time}</p>
              </div>
            </div>
          )}
        </div>
      </main>

      <footer className="border-t border-gray-200 bg-white p-4 text-center text-sm text-gray-400">
        © {new Date().getFullYear()} CRM
      </footer>
    </div>
  );
}
