import { useEffect, useState } from "react";
import { api, ReferralStatRow } from "../api/client";

const ADMIN_PANEL_BASE_URL = import.meta.env.VITE_ADMIN_PANEL_BASE_URL || "http://localhost:5176";
const PER_PAGE = 50;

type Filter = "all" | "clients" | "employees";
type Sort = "applications" | "clicks";

export function ReferralStatsPage() {
  const [filter, setFilter] = useState<Filter>("all");
  const [sort, setSort] = useState<Sort>("applications");
  const [page, setPage] = useState(1);
  const [results, setResults] = useState<ReferralStatRow[]>([]);
  const [count, setCount] = useState(0);
  const [error, setError] = useState("");
  const [copiedIdx, setCopiedIdx] = useState<number | null>(null);
  const [showToast, setShowToast] = useState(false);

  useEffect(() => {
    api
      .referralStats({ filter, sort, page, per_page: PER_PAGE })
      .then((data) => {
        setResults(data.results);
        setCount(data.count);
        setError("");
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Ошибка запроса"));
  }, [filter, sort, page]);

  function changeFilter(next: Filter) {
    setFilter(next);
    setPage(1);
  }

  function changeSort(next: Sort) {
    setSort(next);
    setPage(1);
  }

  async function copy(idx: number, link: string) {
    try {
      await navigator.clipboard.writeText(link);
      setCopiedIdx(idx);
      setShowToast(true);
      setTimeout(() => {
        setShowToast(false);
        setCopiedIdx(null);
      }, 2000);
    } catch (e) {
      alert("Ошибка копирования: " + e);
    }
  }

  const totalPages = Math.max(1, Math.ceil(count / PER_PAGE));

  return (
    <div className="flex min-h-screen flex-col bg-gray-100">
      <header className="bg-white p-4 shadow">
        <div className="mx-auto flex max-w-7xl items-center justify-between">
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
          <h2 className="mb-6 text-2xl font-bold">📊 Статистика по реферальным ссылкам</h2>

          <div className="mb-6 flex flex-wrap items-center gap-4">
            <div className="space-x-2">
              {([
                ["all", "Все"],
                ["clients", "Клиенты"],
                ["employees", "Сотрудники"],
              ] as [Filter, string][]).map(([value, label]) => (
                <button
                  key={value}
                  onClick={() => changeFilter(value)}
                  className={`rounded-lg px-4 py-2 font-medium transition ${
                    filter === value ? "bg-blue-600 text-white shadow" : "bg-gray-200 text-gray-700 hover:bg-gray-300"
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>

            <div className="ml-auto">
              <label htmlFor="sort" className="mr-2 font-medium">
                Сортировать по:
              </label>
              <select
                id="sort"
                value={sort}
                onChange={(e) => changeSort(e.target.value as Sort)}
                className="rounded-lg border bg-white px-3 py-2 shadow-sm"
              >
                <option value="applications">Заявкам</option>
                <option value="clicks">Кликам</option>
              </select>
            </div>
          </div>

          {error && <p className="mb-4 text-red-600">{error}</p>}

          <div className="overflow-x-auto rounded-xl bg-white shadow">
            <table className="min-w-full border-collapse text-left">
              <thead className="bg-gray-100 text-sm uppercase tracking-wider text-gray-700">
                <tr>
                  <th className="p-3">Тип</th>
                  <th className="p-3">Имя</th>
                  <th className="p-3">Реферальная ссылка</th>
                  <th className="p-3 text-center">Клики</th>
                  <th className="p-3 text-center">Заявки</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {results.length === 0 && (
                  <tr>
                    <td colSpan={5} className="p-6 text-center text-gray-500">
                      Нет данных для отображения
                    </td>
                  </tr>
                )}
                {results.map((row, idx) => (
                  <tr key={`${row.type}-${row.name}-${idx}`} className="transition hover:bg-gray-50">
                    <td className="p-3 font-medium text-gray-600">{row.type}</td>
                    <td className="p-3">{row.name}</td>
                    <td className="p-3">
                      <button
                        onClick={() => copy(idx, row.ref_link)}
                        className="rounded-lg bg-blue-600 px-3 py-1 text-sm text-white shadow transition hover:bg-blue-700"
                      >
                        {copiedIdx === idx ? "Скопировано!" : "Скопировать"}
                      </button>
                    </td>
                    <td className="p-3 text-center font-semibold">{row.clicks}</td>
                    <td className="p-3 text-center font-semibold">{row.applications}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {totalPages > 1 && (
            <div className="mt-6 flex items-center justify-center gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
                className="rounded-lg bg-gray-200 px-4 py-2 font-medium text-gray-700 transition hover:bg-gray-300 disabled:cursor-not-allowed disabled:opacity-50"
              >
                ← Назад
              </button>
              <span className="px-2 font-medium text-gray-700">
                Страница {page} из {totalPages}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages}
                className="rounded-lg bg-gray-200 px-4 py-2 font-medium text-gray-700 transition hover:bg-gray-300 disabled:cursor-not-allowed disabled:opacity-50"
              >
                Вперёд →
              </button>
            </div>
          )}
        </div>
      </main>

      <footer className="bg-white p-4 text-center text-sm text-gray-500 shadow">
        © {new Date().getFullYear()} CRM
      </footer>

      {showToast && (
        <div className="fixed bottom-6 right-6 rounded-lg bg-green-600 px-4 py-2 text-white shadow-lg">
          ✅ Ссылка скопирована!
        </div>
      )}
    </div>
  );
}
