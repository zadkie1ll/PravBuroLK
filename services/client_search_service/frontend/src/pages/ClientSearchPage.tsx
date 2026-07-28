import { FormEvent, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, ClientResult } from "../api/client";

const ADMIN_PANEL_BASE_URL = import.meta.env.VITE_ADMIN_PANEL_BASE_URL || "http://localhost:5176";

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
    <div className="flex min-h-screen flex-col bg-gray-100">
      <header className="bg-white p-4 shadow">
        <div className="mx-auto flex max-w-7xl items-center justify-between">
          <h1 className="text-2xl font-bold text-gray-800">Поиск клиентов</h1>
          <a
            href={`${ADMIN_PANEL_BASE_URL}/admin`}
            className="rounded-full bg-gradient-to-r from-blue-400 to-blue-600 px-4 py-2 text-sm font-semibold text-white shadow transition hover:from-blue-500 hover:to-blue-700"
          >
            Назад в меню
          </a>
        </div>
      </header>

      <section className="mx-auto mt-6 w-full max-w-3xl px-4">
        <form onSubmit={onSubmit} className="flex flex-col gap-3 sm:flex-row">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Введите имя, фамилию или Bitrix ID"
            className="flex-1 rounded-lg border border-gray-300 p-3 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <button
            type="submit"
            className="rounded-lg bg-blue-600 px-6 py-3 text-white transition duration-200 hover:bg-blue-700"
          >
            Поиск
          </button>
        </form>
        {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
      </section>

      <section className="mx-auto mt-8 w-full max-w-7xl flex-1 px-4">
        {results.length > 0 && (
          <>
            <h2 className="mb-4 text-lg font-semibold text-gray-700">Результаты поиска</h2>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {results.map((client) => (
                <Link
                  key={client.id}
                  to={`/clients/${client.id}`}
                  className="block rounded-lg bg-white p-5 shadow transition duration-200 hover:shadow-lg"
                >
                  <h3 className="text-xl font-bold text-gray-800">
                    {client.surname} {client.name}
                    {client.middlename ? ` ${client.middlename}` : ""}
                  </h3>
                  <p className="mt-1 text-gray-500">Bitrix ID: {client.bitrix_id || "None"}</p>
                  {client.stage_name && (
                    <p className="mt-2 w-fit rounded-full bg-blue-100 px-3 py-1 text-sm text-blue-800">
                      {client.stage_name}
                    </p>
                  )}
                </Link>
              ))}
            </div>
          </>
        )}
        {searched && results.length === 0 && submittedQuery && (
          <p className="mt-4 text-gray-500">Ничего не найдено</p>
        )}
      </section>

      <footer className="mt-10 bg-white p-4 text-center text-sm text-gray-500 shadow">
        © {new Date().getFullYear()} CRM
      </footer>
    </div>
  );
}
