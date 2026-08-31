import { useEffect, useState } from "react";
import { api, ReferralStatRow } from "../api/client";

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
    <div className="flex min-h-screen flex-col bg-[#f7f7f8] text-[#1c1c1e]">
      <header className="border-b border-gray-200 bg-white">
        <div className="mx-auto max-w-6xl px-6 py-4">
          <h1 className="text-base font-semibold">Статистика</h1>
        </div>
      </header>

      <main className="mx-auto w-full max-w-6xl flex-1 px-6 py-6">
        <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
          <h2 className="mb-6 text-lg font-semibold">Статистика по реферальным ссылкам</h2>

          <div className="mb-5 flex flex-wrap items-center gap-4">
            <div className="flex gap-1 rounded-lg bg-[#f2f2f3] p-1">
              {([
                ["all", "Все"],
                ["clients", "Клиенты"],
                ["employees", "Сотрудники"],
              ] as [Filter, string][]).map(([value, label]) => (
                <button
                  key={value}
                  onClick={() => changeFilter(value)}
                  className={`rounded-md px-3 py-1.5 text-sm font-medium transition ${
                    filter === value ? "bg-white text-[#1c1c1e] shadow-sm" : "text-gray-500 hover:text-[#1c1c1e]"
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>

            <div className="ml-auto flex items-center gap-2">
              <label htmlFor="sort" className="text-sm font-medium text-gray-500">
                Сортировать по:
              </label>
              <select
                id="sort"
                value={sort}
                onChange={(e) => changeSort(e.target.value as Sort)}
                className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm text-[#1c1c1e] focus:border-gray-500 focus:outline-none focus:ring-1 focus:ring-gray-500"
              >
                <option value="applications">Заявкам</option>
                <option value="clicks">Кликам</option>
              </select>
            </div>
          </div>

          {error && <p className="mb-4 text-sm text-red-600">{error}</p>}

          <div className="overflow-hidden rounded-xl border border-gray-200">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="bg-gray-50 text-xs font-semibold uppercase tracking-wide text-gray-500">
                  <th className="px-4 py-3">Тип</th>
                  <th className="px-4 py-3">Имя</th>
                  <th className="px-4 py-3">Реферальная ссылка</th>
                  <th className="px-4 py-3 text-center">Клики</th>
                  <th className="px-4 py-3 text-center">Заявки</th>
                </tr>
              </thead>
              <tbody>
                {results.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-4 py-6 text-center text-gray-400">
                      Нет данных для отображения
                    </td>
                  </tr>
                )}
                {results.map((row, idx) => (
                  <tr key={`${row.type}-${row.name}-${idx}`} className="border-t border-gray-100 hover:bg-gray-50">
                    <td className="px-4 py-2.5 text-gray-500">{row.type}</td>
                    <td className="px-4 py-2.5 font-medium text-[#1c1c1e]">{row.name}</td>
                    <td className="px-4 py-2.5">
                      <button
                        onClick={() => copy(idx, row.ref_link)}
                        className="rounded-md bg-gray-100 px-3 py-1 text-xs font-medium text-gray-700 transition hover:bg-gray-200"
                      >
                        {copiedIdx === idx ? "Скопировано!" : "Скопировать"}
                      </button>
                    </td>
                    <td className="px-4 py-2.5 text-center font-medium text-[#1c1c1e]">{row.clicks}</td>
                    <td className="px-4 py-2.5 text-center font-medium text-[#1c1c1e]">{row.applications}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {totalPages > 1 && (
            <div className="mt-4 flex items-center justify-center gap-4">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
                className="rounded-md px-3 py-1.5 text-sm font-medium text-gray-600 hover:bg-gray-100 disabled:opacity-30"
              >
                ← Назад
              </button>
              <span className="text-sm text-gray-500">
                Страница {page} из {totalPages}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages}
                className="rounded-md px-3 py-1.5 text-sm font-medium text-gray-600 hover:bg-gray-100 disabled:opacity-30"
              >
                Вперёд →
              </button>
            </div>
          )}
        </div>
      </main>

      <footer className="border-t border-gray-200 bg-white p-4 text-center text-sm text-gray-400">
        © {new Date().getFullYear()} CRM
      </footer>

      {showToast && (
        <div className="fixed bottom-6 right-6 rounded-lg bg-[#1c1c1e] px-4 py-2 text-sm font-medium text-white shadow-lg">
          Ссылка скопирована
        </div>
      )}
    </div>
  );
}
