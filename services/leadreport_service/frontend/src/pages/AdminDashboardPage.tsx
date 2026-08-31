import { FormEvent, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, DashboardResponse } from "../api/client";

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

const inputClass =
  "w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-[#1c1c1e] focus:border-gray-500 focus:outline-none focus:ring-1 focus:ring-gray-500";
const cardClass = "rounded-xl border border-gray-200 bg-white p-6 shadow-sm";

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

  return (
    <div className="min-h-screen bg-[#f7f7f8] text-[#1c1c1e]">
      <header className="border-b border-gray-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <h1 className="text-base font-semibold">Статистика менеджеров</h1>
          <Link to="/admin/leadreport" className="text-sm font-medium text-gray-500 transition hover:text-[#1c1c1e]">
            Справочники
          </Link>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-6 py-6">
        {error && <div className="mb-6 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">{error}</div>}

        <section className="grid gap-6 lg:grid-cols-[1.15fr_0.85fr]">
          <div className={cardClass}>
            <p className="text-sm text-gray-500">Сводка по звонкам менеджеров за выбранный период.</p>
            <div className="mt-5 grid gap-4 sm:grid-cols-3">
              <div className="rounded-xl border border-gray-200 bg-[#f7f7f8] p-4">
                <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">Менеджеров</p>
                <p className="mt-1 text-2xl font-semibold text-[#1c1c1e]">{data?.stats.length ?? 0}</p>
              </div>
              <div className="rounded-xl border border-gray-200 bg-[#f7f7f8] p-4">
                <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">Период с</p>
                <p className="mt-1 text-base font-medium text-[#1c1c1e]">
                  {data ? new Date(data.period_start).toLocaleDateString("ru-RU") : "—"}
                </p>
              </div>
              <div className="rounded-xl border border-gray-200 bg-[#f7f7f8] p-4">
                <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">Период по</p>
                <p className="mt-1 text-base font-medium text-[#1c1c1e]">
                  {data ? new Date(data.period_end).toLocaleDateString("ru-RU") : "—"}
                </p>
              </div>
            </div>
          </div>

          <div className={cardClass}>
            <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">Фильтр</p>
            <form onSubmit={handleSubmit} className="mt-4 space-y-3">
              <div>
                <label htmlFor="start" className="mb-1 block text-xs font-semibold uppercase tracking-wide text-gray-500">
                  С даты
                </label>
                <input id="start" type="date" value={start} onChange={(e) => setStart(e.target.value)} className={inputClass} />
              </div>
              <div>
                <label htmlFor="end" className="mb-1 block text-xs font-semibold uppercase tracking-wide text-gray-500">
                  По дату
                </label>
                <input id="end" type="date" value={end} onChange={(e) => setEnd(e.target.value)} className={inputClass} />
              </div>
              <button
                type="submit"
                className="w-full rounded-lg bg-[#1c1c1e] px-4 py-2 text-sm font-medium text-white transition hover:bg-[#333]"
              >
                Обновить отчёт
              </button>
            </form>
          </div>
        </section>

        <section className="mt-6 overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">
                  <th className="px-4 py-3">Менеджер</th>
                  <th className="px-4 py-3">Bitrix ID</th>
                  <th className="px-4 py-3 text-center">Звонки</th>
                  <th className="px-4 py-3 text-center">Время</th>
                  <th className="px-4 py-3 text-right">Детали</th>
                </tr>
              </thead>
              <tbody>
                {data && data.stats.length > 0 ? (
                  data.stats.map((entry) => (
                    <tr key={entry.manager.id} className="border-t border-gray-100 hover:bg-gray-50">
                      <td className="px-4 py-2.5 font-medium text-[#1c1c1e]">{entry.manager.name}</td>
                      <td className="px-4 py-2.5 text-gray-500">{entry.manager.bitrix_user_id}</td>
                      <td className="px-4 py-2.5 text-center">
                        <span className="inline-flex min-w-14 justify-center rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-medium text-gray-700">
                          {entry.call_count}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 text-center font-medium text-[#1c1c1e]">{entry.total_time}</td>
                      <td className="px-4 py-2.5 text-right">
                        <Link
                          to={`/admin/manager/${entry.manager.id}`}
                          className="rounded-md px-3 py-1.5 text-xs font-medium text-gray-600 transition hover:bg-gray-100"
                        >
                          Подробно
                        </Link>
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={5} className="px-4 py-10 text-center text-gray-400">
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
