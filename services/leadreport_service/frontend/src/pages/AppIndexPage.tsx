import { Link } from "react-router-dom";

export function AppIndexPage() {
  return (
    <div className="min-h-screen bg-[#f7f7f8] text-[#1c1c1e]">
      <header className="border-b border-gray-200 bg-white">
        <div className="mx-auto max-w-6xl px-6 py-4">
          <h1 className="text-base font-semibold">Справочники</h1>
        </div>
      </header>

      <main className="mx-auto max-w-2xl px-6 py-6">
        <div className="grid gap-4 sm:grid-cols-2">
          <Link
            to="/admin/managers-list"
            className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm transition hover:shadow-md"
          >
            <h2 className="text-base font-semibold text-[#1c1c1e]">Менеджеры</h2>
            <p className="mt-1 text-sm text-gray-500">Список менеджеров по продажам, синк с Bitrix</p>
          </Link>
          <Link
            to="/admin/sources-list"
            className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm transition hover:shadow-md"
          >
            <h2 className="text-base font-semibold text-[#1c1c1e]">Источники лидов</h2>
            <p className="mt-1 text-sm text-gray-500">Список источников, синк с Bitrix</p>
          </Link>
        </div>
      </main>
    </div>
  );
}
