import { FormEvent, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, ManagerStats } from "../api/client";

function toLocalInput(iso: string): string {
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

const inputClass =
  "w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-[#1c1c1e] focus:border-gray-500 focus:outline-none focus:ring-1 focus:ring-gray-500";

export function AdminManagerDetailPage() {
  const { managerId } = useParams();
  const [stats, setStats] = useState<ManagerStats | null>(null);
  const [error, setError] = useState("");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");

  function load(s?: string, e?: string) {
    if (!managerId) return;
    setError("");
    api
      .adminManagerDetail(Number(managerId), s, e)
      .then((res) => {
        setStats(res);
        setStart(toLocalInput(res.period_start));
        setEnd(toLocalInput(res.period_end));
      })
      .catch((err) => setError(err.message));
  }

  useEffect(() => load(), [managerId]); // eslint-disable-line react-hooks/exhaustive-deps

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    load(start, end);
  }

  return (
    <div className="min-h-screen bg-[#f7f7f8] text-[#1c1c1e]">
      <main className="mx-auto max-w-6xl px-6 py-8">
        {error && <div className="mb-6 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">{error}</div>}

        <div className="flex flex-col gap-4 rounded-xl border border-gray-200 bg-white p-6 shadow-sm md:flex-row md:items-start md:justify-between">
          <div>
            <Link to="/admin" className="text-sm font-medium text-gray-500 transition hover:text-[#1c1c1e]">
              ← К общему отчёту
            </Link>
            {stats && (
              <>
                <h1 className="mt-3 text-xl font-semibold text-[#1c1c1e]">{stats.manager.name}</h1>
                <p className="mt-1 text-sm text-gray-500">Bitrix ID: {stats.manager.bitrix_user_id}</p>
                {stats.manager.email && <p className="mt-0.5 text-sm text-gray-500">{stats.manager.email}</p>}
                {stats.manager.phone && <p className="mt-0.5 text-sm text-gray-500">{stats.manager.phone}</p>}
              </>
            )}
          </div>

          <form onSubmit={handleSubmit} className="w-full rounded-xl border border-gray-200 bg-[#f7f7f8] p-4 md:max-w-md">
            <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">Период</p>
            <div className="mt-3 space-y-3">
              <div>
                <label htmlFor="start" className="mb-1 block text-xs font-semibold uppercase tracking-wide text-gray-500">
                  С
                </label>
                <input id="start" type="datetime-local" value={start} onChange={(e) => setStart(e.target.value)} className={inputClass} />
              </div>
              <div>
                <label htmlFor="end" className="mb-1 block text-xs font-semibold uppercase tracking-wide text-gray-500">
                  По
                </label>
                <input id="end" type="datetime-local" value={end} onChange={(e) => setEnd(e.target.value)} className={inputClass} />
              </div>
              <button
                type="submit"
                className="w-full rounded-lg bg-[#1c1c1e] px-4 py-2 text-sm font-medium text-white transition hover:bg-[#333]"
              >
                Обновить
              </button>
            </div>
          </form>
        </div>

        <section className="mt-6 grid gap-4 md:grid-cols-2">
          <article className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
            <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">Звонки</p>
            <p className="mt-3 text-4xl font-semibold text-[#1c1c1e]">{stats?.call_count ?? 0}</p>
            <p className="mt-2 text-sm text-gray-500">Количество завершённых звонков за выбранный период.</p>
          </article>

          <article className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
            <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">Общее время</p>
            <p className="mt-3 text-4xl font-semibold text-[#1c1c1e]">{stats?.total_time ?? "0"}</p>
            <p className="mt-2 text-sm text-gray-500">Суммарная длительность разговоров менеджера.</p>
          </article>
        </section>
      </main>
    </div>
  );
}
