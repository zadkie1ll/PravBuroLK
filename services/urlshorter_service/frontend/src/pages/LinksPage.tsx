import { useEffect, useState } from "react";
import { MarketingLinkListItem, MarketingLinksFilters, marketingApi } from "../api/client";

const inputClass =
  "mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-[#1c1c1e] shadow-sm focus:border-gray-500 focus:outline-none focus:ring-1 focus:ring-gray-500";
const labelClass = "block text-sm font-medium text-gray-700";

type SortBy = "created_at" | "clicks";
type SortDir = "asc" | "desc";

export function LinksPage() {
  const [items, setItems] = useState<MarketingLinkListItem[]>([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalItems, setTotalItems] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  const [sortBy, setSortBy] = useState<SortBy>("created_at");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [createdFrom, setCreatedFrom] = useState("");
  const [createdTo, setCreatedTo] = useState("");
  const [clicksMin, setClicksMin] = useState("");
  const [clicksMax, setClicksMax] = useState("");

  function buildFilters(p: number): MarketingLinksFilters {
    return {
      page: p,
      sort_by: sortBy,
      sort_dir: sortDir,
      created_from: createdFrom || undefined,
      created_to: createdTo || undefined,
      clicks_min: clicksMin ? Number(clicksMin) : undefined,
      clicks_max: clicksMax ? Number(clicksMax) : undefined,
    };
  }

  function load(p: number) {
    setLoading(true);
    setError(null);
    marketingApi
      .listLinks(buildFilters(p))
      .then((res) => {
        setItems(res.items);
        setPage(res.page);
        setTotalPages(res.total_pages);
        setTotalItems(res.total_items);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Ошибка загрузки"))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    load(1);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sortBy, sortDir]);

  function toggleSort(field: SortBy) {
    if (sortBy === field) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortBy(field);
      setSortDir("desc");
    }
  }

  function sortIndicator(field: SortBy) {
    if (sortBy !== field) return "";
    return sortDir === "asc" ? " ▲" : " ▼";
  }

  async function handleDelete(item: MarketingLinkListItem) {
    if (!window.confirm(`Удалить ссылку ${item.public_link}?`)) return;
    setDeletingId(item.id);
    try {
      await marketingApi.deleteLink(item.id);
      setItems((prev) => prev.filter((i) => i.id !== item.id));
      setTotalItems((n) => n - 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось удалить ссылку");
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold">Управление ссылками</h2>
        <span className="text-sm text-gray-500">Всего: {totalItems}</span>
      </div>

      <div className="mb-4 grid grid-cols-2 gap-3 rounded-lg bg-gray-50 p-4 sm:grid-cols-4">
        <div>
          <label className={labelClass}>Дата создания — с</label>
          <input type="date" className={inputClass} value={createdFrom} onChange={(e) => setCreatedFrom(e.target.value)} />
        </div>
        <div>
          <label className={labelClass}>Дата создания — по</label>
          <input type="date" className={inputClass} value={createdTo} onChange={(e) => setCreatedTo(e.target.value)} />
        </div>
        <div>
          <label className={labelClass}>Клики — от</label>
          <input
            type="number"
            min={0}
            className={inputClass}
            value={clicksMin}
            onChange={(e) => setClicksMin(e.target.value)}
          />
        </div>
        <div>
          <label className={labelClass}>Клики — до</label>
          <input
            type="number"
            min={0}
            className={inputClass}
            value={clicksMax}
            onChange={(e) => setClicksMax(e.target.value)}
          />
        </div>
        <div className="col-span-2 sm:col-span-4">
          <button
            onClick={() => load(1)}
            className="rounded-lg bg-[#1c1c1e] px-4 py-2 text-sm font-medium text-white transition hover:bg-[#333]"
          >
            Применить фильтр
          </button>
        </div>
      </div>

      {error && <p className="mb-3 rounded-lg bg-red-50 p-3 text-sm text-red-600">{error}</p>}

      {loading ? (
        <p className="text-sm text-gray-500">Загрузка...</p>
      ) : items.length === 0 ? (
        <p className="text-sm text-gray-500">Ссылок не найдено.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-gray-200 text-xs uppercase text-gray-500">
                <th className="py-2 pr-4">Ссылка</th>
                <th className="py-2 pr-4">Назначение</th>
                <th className="py-2 pr-4">utm_campaign</th>
                <th className="cursor-pointer select-none py-2 pr-4" onClick={() => toggleSort("clicks")}>
                  Клики{sortIndicator("clicks")}
                </th>
                <th className="cursor-pointer select-none whitespace-nowrap py-2 pr-4" onClick={() => toggleSort("created_at")}>
                  Создана{sortIndicator("created_at")}
                </th>
                <th className="py-2" />
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id} className="border-b border-gray-100 align-top">
                  <td className="max-w-xs break-all py-2 pr-4 font-mono text-xs">{item.public_link}</td>
                  <td className="max-w-xs break-all py-2 pr-4 text-gray-600">{item.destination}</td>
                  <td className="py-2 pr-4">{item.utm_campaign}</td>
                  <td className="py-2 pr-4">{item.clicks}</td>
                  <td className="whitespace-nowrap py-2 pr-4 text-gray-500">
                    {new Date(item.created_at).toLocaleDateString("ru-RU")}
                  </td>
                  <td className="py-2">
                    <button
                      onClick={() => handleDelete(item)}
                      disabled={deletingId === item.id}
                      className="rounded-lg border border-red-200 px-3 py-1 text-xs font-medium text-red-600 transition hover:bg-red-50 disabled:opacity-50"
                    >
                      {deletingId === item.id ? "Удаление..." : "Удалить"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {totalPages > 1 && (
        <div className="mt-4 flex items-center justify-center gap-3 text-sm">
          <button
            onClick={() => load(page - 1)}
            disabled={page <= 1}
            className="rounded-lg border border-gray-200 px-3 py-1 disabled:opacity-40"
          >
            Назад
          </button>
          <span className="text-gray-500">
            {page} / {totalPages}
          </span>
          <button
            onClick={() => load(page + 1)}
            disabled={page >= totalPages}
            className="rounded-lg border border-gray-200 px-3 py-1 disabled:opacity-40"
          >
            Вперёд
          </button>
        </div>
      )}
    </div>
  );
}
