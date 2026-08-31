import { useEffect, useState } from "react";
import { PaymentsDashboardResponse, api } from "../api/client";

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
    <div className="flex min-h-screen flex-col bg-[#f7f7f8] text-[#1c1c1e]">
      <header className="border-b border-gray-200 bg-white">
        <div className="mx-auto max-w-6xl px-6 py-4">
          {/* Заголовок "Статистика посещений ЛК" — так же, как в оригинальном
              payments_stats.html (там h1 всегда так называется, а title вкладки —
              "Админ-панель — Фактические платежи"; это не опечатка, а как в проде). */}
          <h1 className="text-base font-semibold">Статистика посещений ЛК</h1>
        </div>
      </header>

      <main className="mx-auto w-full max-w-6xl flex-1 px-6 py-6">
        <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
          <h2 className="mb-6 text-lg font-semibold">Статистика фактических платежей</h2>

          {error && <p className="mb-4 text-sm text-red-600">{error}</p>}

          {data && (
            <>
              <div className="mb-10 grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
                <div className="rounded-xl border border-gray-200 bg-[#f7f7f8] p-5 text-center">
                  <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-gray-500">Сегодня</p>
                  <p className="text-xl font-semibold text-[#1c1c1e]">{data.stats.day} ₽</p>
                </div>
                <div className="rounded-xl border border-gray-200 bg-[#f7f7f8] p-5 text-center">
                  <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-gray-500">Неделя</p>
                  <p className="text-xl font-semibold text-[#1c1c1e]">{data.stats.week} ₽</p>
                </div>
                <div className="rounded-xl border border-gray-200 bg-[#f7f7f8] p-5 text-center">
                  <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-gray-500">Месяц</p>
                  <p className="text-xl font-semibold text-[#1c1c1e]">{data.stats.month} ₽</p>
                </div>
                <div className="rounded-xl border border-gray-200 bg-[#f7f7f8] p-5 text-center">
                  <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-gray-500">Год</p>
                  <p className="text-xl font-semibold text-[#1c1c1e]">{data.stats.year} ₽</p>
                </div>
              </div>

              <h3 className="mb-4 text-sm font-semibold text-gray-500">Последние платежи</h3>

              <div className="overflow-hidden rounded-xl border border-gray-200">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-gray-50 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">
                      <th className="px-4 py-3">Дата</th>
                      <th className="px-4 py-3">Сумма</th>
                      <th className="px-4 py-3">План</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.results.length === 0 && (
                      <tr>
                        <td colSpan={3} className="px-4 py-4 text-center text-gray-400">
                          Нет фактических платежей
                        </td>
                      </tr>
                    )}
                    {data.results.map((p, idx) => (
                      <tr key={idx} className="border-t border-gray-100 hover:bg-gray-50">
                        <td className="px-4 py-2.5">{p.payment_date ? formatDate(p.payment_date) : "—"}</td>
                        <td className="px-4 py-2.5 font-medium text-[#1c1c1e]">{p.amount} ₽</td>
                        <td className="px-4 py-2.5">{p.client_name || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {data.num_pages > 1 && (
                <div className="mt-4 flex items-center justify-center gap-4">
                  <button
                    disabled={page <= 1}
                    onClick={() => setPage((p) => p - 1)}
                    className="rounded-md px-3 py-1.5 text-sm font-medium text-gray-600 hover:bg-gray-100 disabled:opacity-30"
                  >
                    ← Предыдущая
                  </button>
                  <span className="text-sm text-gray-500">
                    Страница {data.page} из {data.num_pages}
                  </span>
                  <button
                    disabled={page >= data.num_pages}
                    onClick={() => setPage((p) => p + 1)}
                    className="rounded-md px-3 py-1.5 text-sm font-medium text-gray-600 hover:bg-gray-100 disabled:opacity-30"
                  >
                    Следующая →
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      </main>

      <footer className="border-t border-gray-200 bg-white p-4 text-center text-sm text-gray-400">
        © {new Date().getFullYear()} CRM
      </footer>
    </div>
  );
}
