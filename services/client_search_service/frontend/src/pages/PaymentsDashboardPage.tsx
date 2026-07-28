import { useEffect, useState } from "react";
import { PaymentsDashboardResponse, api } from "../api/client";

const ADMIN_PANEL_BASE_URL = import.meta.env.VITE_ADMIN_PANEL_BASE_URL || "http://localhost:5176";

function formatDate(isoDate: string): string {
  const [year, month, day] = isoDate.split("-");
  return `${day}.${month}.${year}`;
}

export function PaymentsDashboardPage() {
  const [page, setPage] = useState(1);
  const [data, setData] = useState<PaymentsDashboardResponse | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .paymentsDashboard(page)
      .then(setData)
      .catch((e) => setError(e instanceof Error ? e.message : "Ошибка запроса"));
  }, [page]);

  return (
    <div className="flex min-h-screen flex-col bg-gray-100">
      <header className="bg-white p-4 shadow">
        <div className="mx-auto flex max-w-7xl items-center justify-between">
          {/* Заголовок "Статистика посещений ЛК" — так же, как в оригинальном
              payments_stats.html (там h1 всегда так называется, а title вкладки —
              "Админ-панель — Фактические платежи"; это не опечатка, а как в проде). */}
          <h1 className="text-2xl font-bold text-gray-800">Статистика посещений ЛК</h1>
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
          <h2 className="mb-8 text-2xl font-semibold text-gray-800">📊 Статистика фактических платежей</h2>

          {error && <p className="mb-4 text-red-600">{error}</p>}

          {data && (
            <>
              <div className="mb-12 grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-4">
                <div className="rounded-xl border border-blue-200 bg-gradient-to-tr from-blue-50 to-blue-100 p-6 text-center shadow">
                  <p className="mb-1 text-sm text-gray-500">Сегодня</p>
                  <p className="text-2xl font-bold text-gray-800">{data.stats.day} ₽</p>
                </div>
                <div className="rounded-xl border border-green-200 bg-gradient-to-tr from-green-50 to-green-100 p-6 text-center shadow">
                  <p className="mb-1 text-sm text-gray-500">Неделя</p>
                  <p className="text-2xl font-bold text-gray-800">{data.stats.week} ₽</p>
                </div>
                <div className="rounded-xl border border-purple-200 bg-gradient-to-tr from-purple-50 to-purple-100 p-6 text-center shadow">
                  <p className="mb-1 text-sm text-gray-500">Месяц</p>
                  <p className="text-2xl font-bold text-gray-800">{data.stats.month} ₽</p>
                </div>
                <div className="rounded-xl border border-orange-200 bg-gradient-to-tr from-orange-50 to-orange-100 p-6 text-center shadow">
                  <p className="mb-1 text-sm text-gray-500">Год</p>
                  <p className="text-2xl font-bold text-gray-800">{data.stats.year} ₽</p>
                </div>
              </div>

              <h3 className="mb-4 text-xl font-semibold text-gray-800">🧾 Последние платежи</h3>

              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200 rounded-lg border shadow">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-3 text-left text-sm font-semibold text-gray-600">Дата</th>
                      <th className="px-4 py-3 text-left text-sm font-semibold text-gray-600">Сумма</th>
                      <th className="px-4 py-3 text-left text-sm font-semibold text-gray-600">План</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {data.results.length === 0 && (
                      <tr>
                        <td colSpan={3} className="px-4 py-4 text-center text-gray-500">
                          Нет фактических платежей
                        </td>
                      </tr>
                    )}
                    {data.results.map((p, idx) => (
                      <tr key={idx} className="transition hover:bg-gray-50">
                        <td className="px-4 py-3 text-sm text-gray-700">
                          {p.payment_date ? formatDate(p.payment_date) : "—"}
                        </td>
                        <td className="px-4 py-3 text-sm font-medium text-gray-800">{p.amount} ₽</td>
                        <td className="px-4 py-3 text-sm text-gray-700">{p.client_name || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {data.num_pages > 1 && (
                <div className="mt-6 flex items-center justify-between">
                  {page > 1 ? (
                    <button
                      onClick={() => setPage((p) => p - 1)}
                      className="rounded-lg bg-gray-200 px-4 py-2 text-sm transition hover:bg-gray-300"
                    >
                      « Предыдущая
                    </button>
                  ) : (
                    <span className="px-4 py-2 text-sm text-gray-400">« Предыдущая</span>
                  )}

                  <span className="text-sm text-gray-600">
                    Страница {data.page} из {data.num_pages}
                  </span>

                  {page < data.num_pages ? (
                    <button
                      onClick={() => setPage((p) => p + 1)}
                      className="rounded-lg bg-gray-200 px-4 py-2 text-sm transition hover:bg-gray-300"
                    >
                      Следующая »
                    </button>
                  ) : (
                    <span className="px-4 py-2 text-sm text-gray-400">Следующая »</span>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      </main>

      <footer className="bg-white p-4 text-center text-sm text-gray-500 shadow">
        © {new Date().getFullYear()} CRM
      </footer>
    </div>
  );
}
