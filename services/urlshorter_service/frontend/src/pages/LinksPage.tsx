import { useEffect, useState } from "react";
import { MarketingLinkListItem, marketingApi } from "../api/client";

export function LinksPage() {
  const [items, setItems] = useState<MarketingLinkListItem[]>([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalItems, setTotalItems] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  function load(p: number) {
    setLoading(true);
    setError(null);
    marketingApi
      .listLinks(p)
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
  }, []);

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
        <h2 className="text-lg font-semibold">Все ссылки</h2>
        <span className="text-sm text-gray-500">Всего: {totalItems}</span>
      </div>

      {error && <p className="mb-3 rounded-lg bg-red-50 p-3 text-sm text-red-600">{error}</p>}

      {loading ? (
        <p className="text-sm text-gray-500">Загрузка...</p>
      ) : items.length === 0 ? (
        <p className="text-sm text-gray-500">Ссылок пока нет.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-gray-200 text-xs uppercase text-gray-500">
                <th className="py-2 pr-4">Ссылка</th>
                <th className="py-2 pr-4">Назначение</th>
                <th className="py-2 pr-4">utm_campaign</th>
                <th className="py-2 pr-4">Клики</th>
                <th className="py-2 pr-4">Создана</th>
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
