import { FormEvent, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, LeadSourceAdminRow, LeadSourceListResponse } from "../api/client";

const FILTERS: { value: "" | "true" | "false"; label: string }[] = [
  { value: "", label: "Все" },
  { value: "true", label: "Активные" },
  { value: "false", label: "Неактивные" },
];

export function SourcesListPage() {
  const [data, setData] = useState<LeadSourceListResponse | null>(null);
  const [search, setSearch] = useState("");
  const [activeFilter, setActiveFilter] = useState<"" | "true" | "false">("");
  const [page, setPage] = useState(1);
  const [error, setError] = useState("");
  const [syncMessage, setSyncMessage] = useState("");

  function load() {
    setError("");
    api
      .sourcesList({ search, is_active: activeFilter === "" ? undefined : activeFilter === "true", page })
      .then(setData)
      .catch((err) => setError(err.message));
  }

  useEffect(load, [activeFilter, page]); // eslint-disable-line react-hooks/exhaustive-deps

  function handleSearchSubmit(event: FormEvent) {
    event.preventDefault();
    setPage(1);
    load();
  }

  async function toggleActive(row: LeadSourceAdminRow) {
    try {
      await api.patchSourceActive(row.id, !row.is_active);
      load();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function syncFromBitrix() {
    setSyncMessage("Обновление...");
    try {
      const result = await api.syncSources();
      setSyncMessage(
        `Из Bitrix: ${result.total_from_bitrix}. Создано: ${result.created}, обновлено: ${result.updated}, деактивировано: ${result.deactivated}.`,
      );
      load();
    } catch (err) {
      setSyncMessage(`Ошибка: ${(err as Error).message}`);
    }
  }

  const totalPages = data ? Math.max(1, Math.ceil(data.count / data.per_page)) : 1;

  return (
    <div className="min-h-screen bg-[#f7f7f8] text-[#1c1c1e]">
      <header className="border-b border-gray-200 bg-white">
        <div className="mx-auto max-w-6xl px-6 py-4">
          <Link to="/admin/leadreport" className="text-xs font-medium text-gray-400 hover:text-gray-600">
            ← Справочники
          </Link>
          <div className="mt-1 flex items-center justify-between">
            <h1 className="text-base font-semibold">Источники лидов</h1>
            <button
              onClick={syncFromBitrix}
              className="rounded-lg bg-[#1c1c1e] px-4 py-2 text-sm font-medium text-white transition hover:bg-[#333]"
            >
              Обновить из Bitrix
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-6 py-6">
        {syncMessage && <p className="mb-4 text-sm text-gray-600">{syncMessage}</p>}
        {error && <p className="mb-4 text-sm text-red-600">{error}</p>}

        <div className="flex flex-wrap items-center gap-4">
          <form onSubmit={handleSearchSubmit} className="flex gap-2">
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Поиск..."
              className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm focus:border-gray-500 focus:outline-none focus:ring-1 focus:ring-gray-500"
            />
            <button type="submit" className="rounded-lg bg-[#1c1c1e] px-4 py-1.5 text-sm font-medium text-white hover:bg-[#333]">
              Найти
            </button>
          </form>

          <div className="ml-auto flex gap-1 rounded-lg bg-[#f2f2f3] p-1">
            {FILTERS.map((f) => (
              <button
                key={f.value}
                onClick={() => {
                  setActiveFilter(f.value);
                  setPage(1);
                }}
                className={`rounded-md px-3 py-1.5 text-sm font-medium transition ${
                  activeFilter === f.value ? "bg-white text-[#1c1c1e] shadow-sm" : "text-gray-500 hover:text-[#1c1c1e]"
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>

        <div className="mt-4 overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="bg-gray-50 text-xs font-semibold uppercase tracking-wide text-gray-500">
                  <th className="px-4 py-3">Имя</th>
                  <th className="px-4 py-3">Bitrix ID</th>
                  <th className="px-4 py-3">Активен</th>
                  <th className="px-4 py-3">Создан</th>
                </tr>
              </thead>
              <tbody>
                {data?.results.map((row) => (
                  <tr key={row.id} className="border-t border-gray-100 hover:bg-gray-50">
                    <td className="px-4 py-2.5 font-medium text-[#1c1c1e]">{row.name}</td>
                    <td className="px-4 py-2.5 text-gray-500">{row.bitrix_id ?? "—"}</td>
                    <td className="px-4 py-2.5">
                      <input type="checkbox" checked={row.is_active} onChange={() => toggleActive(row)} />
                    </td>
                    <td className="px-4 py-2.5 text-gray-500">{new Date(row.created_at).toLocaleString("ru-RU")}</td>
                  </tr>
                ))}
                {data && data.results.length === 0 && (
                  <tr>
                    <td colSpan={4} className="px-4 py-8 text-center text-gray-400">
                      Источников нет
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          {data && (
            <div className="flex items-center justify-between border-t border-gray-100 px-4 py-3 text-sm text-gray-500">
              <span>{data.count} источников</span>
              <div className="flex items-center gap-4">
                <button
                  disabled={page <= 1}
                  onClick={() => setPage((p) => p - 1)}
                  className="rounded-md px-3 py-1.5 font-medium text-gray-600 hover:bg-gray-100 disabled:opacity-30"
                >
                  ← Назад
                </button>
                <span>
                  Страница {page} из {totalPages}
                </span>
                <button
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => p + 1)}
                  className="rounded-md px-3 py-1.5 font-medium text-gray-600 hover:bg-gray-100 disabled:opacity-30"
                >
                  Вперёд →
                </button>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
