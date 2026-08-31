import { FormEvent, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, ClientResult } from "../api/client";

export function ClientSearchPage() {
  const [query, setQuery] = useState("");
  const [submittedQuery, setSubmittedQuery] = useState("");
  const [results, setResults] = useState<ClientResult[]>([]);
  const [searched, setSearched] = useState(false);
  const [error, setError] = useState("");

  // Соответствует client_search_view: пустой q возвращает полный список (order_by surname, name),
  // а не пустой результат — грузим его сразу при открытии страницы.
  useEffect(() => {
    runSearch("");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function runSearch(q: string) {
    try {
      const data = await api.search(q);
      setResults(data.results);
      setSubmittedQuery(data.query);
      setSearched(true);
      setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка запроса");
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    runSearch(query);
  }

  return (
    <div className="flex min-h-screen flex-col bg-[#f7f7f8] text-[#1c1c1e]">
      <header className="border-b border-gray-200 bg-white">
        <div className="mx-auto max-w-6xl px-6 py-4">
          <h1 className="text-base font-semibold">Поиск клиентов</h1>
        </div>
      </header>

      <section className="mx-auto mt-6 w-full max-w-3xl px-6">
        <form onSubmit={onSubmit} className="flex flex-col gap-3 sm:flex-row">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Введите имя, фамилию или Bitrix ID"
            className="flex-1 rounded-lg border border-gray-300 px-3 py-2.5 text-sm text-[#1c1c1e] shadow-sm focus:border-gray-500 focus:outline-none focus:ring-1 focus:ring-gray-500"
          />
          <button
            type="submit"
            className="rounded-lg bg-[#1c1c1e] px-6 py-2.5 text-sm font-medium text-white transition hover:bg-[#333]"
          >
            Поиск
          </button>
        </form>
        {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
      </section>

      <section className="mx-auto mt-8 w-full max-w-6xl flex-1 px-6">
        {results.length > 0 && (
          <>
            <h2 className="mb-4 text-sm font-semibold text-gray-500">Результаты поиска</h2>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {results.map((client) => (
                <Link
                  key={client.id}
                  to={`/clients/${client.id}`}
                  className="block rounded-xl border border-gray-200 bg-white p-5 shadow-sm transition hover:shadow-md"
                >
                  <h3 className="text-base font-semibold text-[#1c1c1e]">
                    {client.surname} {client.name}
                    {client.middlename ? ` ${client.middlename}` : ""}
                  </h3>
                  <p className="mt-1 text-sm text-gray-500">Bitrix ID: {client.bitrix_id || "None"}</p>
                  {client.stage_name && (
                    <p className="mt-2 w-fit rounded-full bg-gray-100 px-3 py-1 text-xs font-medium text-gray-700">
                      {client.stage_name}
                    </p>
                  )}
                </Link>
              ))}
            </div>
          </>
        )}
        {searched && results.length === 0 && submittedQuery && (
          <p className="mt-4 text-sm text-gray-400">Ничего не найдено</p>
        )}
      </section>

      <footer className="mt-10 border-t border-gray-200 bg-white p-4 text-center text-sm text-gray-400">
        © {new Date().getFullYear()} CRM
      </footer>
    </div>
  );
}
