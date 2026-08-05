import { FormEvent, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, clearToken, DashboardResponse } from "../api/client";

const ADMIN_PANEL_BASE_URL = import.meta.env.VITE_ADMIN_PANEL_BASE_URL || "http://localhost:5176";

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

export function AdminDashboardPage() {
  const [data, setData] = useState<DashboardResponse | null>(null);
  const [error, setError] = useState("");
  const [start, setStart] = useState(today());
  const [end, setEnd] = useState(today());

  function load(s = start, e = end) {
    setError("");
    api
      .adminDashboard(s, e)
      .then((res) => {
        setData(res);
        setStart(res.period_start);
        setEnd(res.period_end);
      })
      .catch((err) => setError(err.message));
  }

  useEffect(() => load(), []); // eslint-disable-line react-hooks/exhaustive-deps

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    load(start, end);
  }

  function logout() {
    clearToken();
    window.location.href = `${ADMIN_PANEL_BASE_URL}/admin-panel`;
  }

  return (
    <div className="relative min-h-screen bg-slate-950 text-slate-100">
      <div className="pointer-events-none fixed inset-0 -z-10 bg-[radial-gradient(circle_at_top_left,_rgba(14,165,233,0.16),_transparent_28%),radial-gradient(circle_at_top_right,_rgba(168,85,247,0.14),_transparent_24%),linear-gradient(180deg,_#020617_0%,_#0f172a_100%)]" />

      <header className="border-b border-white/10 bg-slate-950/80 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-5">
          <div>
            <p className="text-xs uppercase tracking-[0.35em] text-cyan-300">Lead Report</p>
            <h1 className="mt-2 text-2xl font-semibold text-white">Статистика менеджеров</h1>
          </div>
          <div className="flex items-center gap-3">
            <Link
              to="/admin/leadreport"
              className="text-sm text-slate-400 transition hover:text-cyan-200"
            >
              Django admin
            </Link>
            <button
              onClick={logout}
              className="rounded-full bg-cyan-400 px-4 py-2 text-sm font-medium text-slate-950 transition hover:bg-cyan-300"
            >
              Выйти
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-6 py-10">
        {error && (
          <div className="mb-6 rounded-2xl border border-red-400/30 bg-red-400/10 p-4 text-red-200">{error}</div>
        )}

        <section className="grid gap-6 lg:grid-cols-[1.15fr_0.85fr]">
          <div className="rounded-3xl border border-white/10 bg-white/5 p-8 shadow-2xl shadow-cyan-950/20 backdrop-blur">
            <p className="text-sm text-slate-300">Сводка по звонкам менеджеров за выбранный период.</p>
            <div className="mt-6 grid gap-4 sm:grid-cols-3">
              <div className="rounded-2xl border border-white/10 bg-slate-900/70 p-5">
                <p className="text-sm text-slate-400">Менеджеров</p>
                <p className="mt-2 text-3xl font-semibold text-white">{data?.stats.length ?? 0}</p>
              </div>
              <div className="rounded-2xl border border-white/10 bg-slate-900/70 p-5">
                <p className="text-sm text-slate-400">Период с</p>
                <p className="mt-2 text-lg font-medium text-white">
                  {data ? new Date(data.period_start).toLocaleDateString("ru-RU") : "—"}
                </p>
              </div>
              <div className="rounded-2xl border border-white/10 bg-slate-900/70 p-5">
                <p className="text-sm text-slate-400">Период по</p>
                <p className="mt-2 text-lg font-medium text-white">
                  {data ? new Date(data.period_end).toLocaleDateString("ru-RU") : "—"}
                </p>
              </div>
            </div>
          </div>

          <div className="rounded-3xl border border-cyan-400/20 bg-cyan-400/10 p-8 shadow-2xl shadow-cyan-950/20">
            <p className="text-sm uppercase tracking-[0.28em] text-cyan-200">Фильтр</p>
            <form onSubmit={handleSubmit} className="mt-5 space-y-4">
              <div>
                <label htmlFor="start" className="mb-2 block text-sm text-slate-300">
                  С даты
                </label>
                <input
                  id="start"
                  type="date"
                  value={start}
                  onChange={(e) => setStart(e.target.value)}
                  className="w-full rounded-2xl border border-white/10 bg-slate-950/70 px-4 py-3 text-slate-100 outline-none transition focus:border-cyan-300"
                />
              </div>
              <div>
                <label htmlFor="end" className="mb-2 block text-sm text-slate-300">
                  По дату
                </label>
                <input
                  id="end"
                  type="date"
                  value={end}
                  onChange={(e) => setEnd(e.target.value)}
                  className="w-full rounded-2xl border border-white/10 bg-slate-950/70 px-4 py-3 text-slate-100 outline-none transition focus:border-cyan-300"
                />
              </div>
              <button
                type="submit"
                className="w-full rounded-2xl bg-white px-4 py-3 font-medium text-slate-950 transition hover:bg-cyan-100"
              >
                Обновить отчет
              </button>
            </form>
          </div>
        </section>

        <section className="mt-8 overflow-hidden rounded-3xl border border-white/10 bg-slate-900/70 shadow-2xl shadow-slate-950/30 backdrop-blur">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-white/10">
              <thead className="bg-white/5">
                <tr className="text-left text-sm uppercase tracking-[0.18em] text-slate-400">
                  <th className="px-6 py-4">Менеджер</th>
                  <th className="px-6 py-4">Bitrix ID</th>
                  <th className="px-6 py-4 text-center">Звонки</th>
                  <th className="px-6 py-4 text-center">Время</th>
                  <th className="px-6 py-4 text-right">Детали</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/10 text-sm text-slate-200">
                {data && data.stats.length > 0 ? (
                  data.stats.map((entry) => (
                    <tr key={entry.manager.id} className="transition hover:bg-white/5">
                      <td className="px-6 py-4">
                        <div className="font-medium text-white">{entry.manager.name}</div>
                      </td>
                      <td className="px-6 py-4 text-slate-400">{entry.manager.bitrix_user_id}</td>
                      <td className="px-6 py-4 text-center">
                        <span className="inline-flex min-w-16 justify-center rounded-full bg-cyan-400/15 px-3 py-1 font-semibold text-cyan-200">
                          {entry.call_count}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-center font-medium text-white">{entry.total_time}</td>
                      <td className="px-6 py-4 text-right">
                        <Link
                          to={`/admin/manager/${entry.manager.id}`}
                          className="inline-flex rounded-full border border-cyan-400/30 px-4 py-2 text-sm text-cyan-200 transition hover:border-cyan-300 hover:bg-cyan-400/10"
                        >
                          Подробно
                        </Link>
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={5} className="px-6 py-12 text-center text-slate-400">
                      Нет активных менеджеров с Bitrix ID.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>
      </main>
    </div>
  );
}
