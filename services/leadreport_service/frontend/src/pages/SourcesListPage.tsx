import { FormEvent, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, LeadSourceAdminRow, LeadSourceListResponse } from "../api/client";

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
    <div className="min-h-screen bg-[#f8f8f8] text-[13px] text-[#333]">
      <div className="bg-[#417690] px-6 py-3 text-white">
        <span className="text-lg">Django administration</span>
      </div>
      <div className="bg-white px-6 py-2 text-xs text-[#666]">
        <Link to="/admin" className="text-[#417690] hover:underline">
          Главная
        </Link>{" "}
        › Leadreport › Lead sources
      </div>

      <div className="mx-auto max-w-6xl px-6 py-6">
        <div className="mb-4 flex items-center justify-between">
          <h1 className="text-xl font-normal text-[#333]">Select lead source to change</h1>
          <button
            onClick={syncFromBitrix}
            className="rounded border border-[#ccc] bg-white px-3 py-1.5 text-sm text-[#333] hover:bg-[#f8f8f8]"
          >
            Обновить источники из Bitrix
          </button>
        </div>
        {syncMessage && <p className="mb-4 text-sm text-[#417690]">{syncMessage}</p>}
        {error && <p className="mb-4 text-sm text-red-600">{error}</p>}

        <div className="flex gap-6">
          <div className="flex-1 rounded border border-[#ccc] bg-white">
            <form onSubmit={handleSearchSubmit} className="flex gap-2 border-b border-[#eee] p-3">
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search"
                className="flex-1 rounded border border-[#ccc] px-2 py-1 text-sm"
              />
              <button type="submit" className="rounded bg-[#417690] px-3 py-1 text-sm text-white hover:bg-[#356179]">
                Search
              </button>
            </form>

            <table className="w-full border-collapse text-left text-sm">
              <thead>
                <tr className="bg-[#79aec8] text-white">
                  <th className="px-3 py-2 font-normal">NAME</th>
                  <th className="px-3 py-2 font-normal">BITRIX ID</th>
                  <th className="px-3 py-2 font-normal">IS ACTIVE</th>
                  <th className="px-3 py-2 font-normal">CREATED AT</th>
                </tr>
              </thead>
              <tbody>
                {data?.results.map((row, i) => (
                  <tr key={row.id} className={i % 2 === 0 ? "bg-white" : "bg-[#f8f8f8]"}>
                    <td className="px-3 py-2">
                      <span className="text-[#417690]">{row.name}</span>
                    </td>
                    <td className="px-3 py-2">{row.bitrix_id ?? "—"}</td>
                    <td className="px-3 py-2">
                      <input type="checkbox" checked={row.is_active} onChange={() => toggleActive(row)} />
                    </td>
                    <td className="px-3 py-2">{new Date(row.created_at).toLocaleString("ru-RU")}</td>
                  </tr>
                ))}
                {data && data.results.length === 0 && (
                  <tr>
                    <td colSpan={4} className="px-3 py-6 text-center text-[#999]">
                      0 lead sources
                    </td>
                  </tr>
                )}
              </tbody>
            </table>

            {data && (
              <div className="flex items-center justify-between border-t border-[#eee] px-3 py-2 text-sm text-[#666]">
                <span>{data.count} lead sources</span>
                <div className="flex gap-2">
                  <button
                    disabled={page <= 1}
                    onClick={() => setPage((p) => p - 1)}
                    className="disabled:opacity-40"
                  >
                    ← Previous
                  </button>
                  <span>
                    Page {page} of {totalPages}
                  </span>
                  <button
                    disabled={page >= totalPages}
                    onClick={() => setPage((p) => p + 1)}
                    className="disabled:opacity-40"
                  >
                    Next →
                  </button>
                </div>
              </div>
            )}
          </div>

          <div className="w-56 shrink-0 rounded border border-[#ccc] bg-white p-3">
            <h3 className="mb-2 text-sm font-semibold text-[#666]">By is active</h3>
            <ul className="space-y-1 text-sm">
              <li>
                <button
                  onClick={() => {
                    setActiveFilter("");
                    setPage(1);
                  }}
                  className={activeFilter === "" ? "font-semibold text-black" : "text-[#417690] hover:underline"}
                >
                  All
                </button>
              </li>
              <li>
                <button
                  onClick={() => {
                    setActiveFilter("true");
                    setPage(1);
                  }}
                  className={activeFilter === "true" ? "font-semibold text-black" : "text-[#417690] hover:underline"}
                >
                  Yes
                </button>
              </li>
              <li>
                <button
                  onClick={() => {
                    setActiveFilter("false");
                    setPage(1);
                  }}
                  className={activeFilter === "false" ? "font-semibold text-black" : "text-[#417690] hover:underline"}
                >
                  No
                </button>
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
