import { FormEvent, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, ManagerStats } from "../api/client";

function toLocalInput(iso: string): string {
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

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
    <div className="relative min-h-screen bg-slate-950 text-slate-100">
      <div className="pointer-events-none fixed inset-0 -z-10 bg-[radial-gradient(circle_at_top,_rgba(34,197,94,0.16),_transparent_26%),linear-gradient(180deg,_#020617_0%,_#111827_100%)]" />

      <main className="mx-auto max-w-6xl px-6 py-10">
        {error && (
          <div className="mb-6 rounded-2xl border border-red-400/30 bg-red-400/10 p-4 text-red-200">{error}</div>
        )}

        <div className="flex flex-col gap-4 rounded-3xl border border-white/10 bg-white/5 p-8 shadow-2xl shadow-emerald-950/20 backdrop-blur md:flex-row md:items-start md:justify-between">
          <div>
            <Link to="/admin" className="text-sm text-emerald-300 transition hover:text-emerald-200">
              ← К общему отчету
            </Link>
            {stats && (
              <>
                <h1 className="mt-4 text-3xl font-semibold text-white">{stats.manager.name}</h1>
                <p className="mt-2 text-slate-300">Bitrix ID: {stats.manager.bitrix_user_id}</p>
                {stats.manager.email && <p className="mt-1 text-slate-400">{stats.manager.email}</p>}
                {stats.manager.phone && <p className="mt-1 text-slate-400">{stats.manager.phone}</p>}
              </>
            )}
          </div>

          <form onSubmit={handleSubmit} className="w-full rounded-3xl border border-white/10 bg-slate-950/60 p-5 md:max-w-md">
            <p className="text-sm uppercase tracking-[0.28em] text-emerald-200">Период</p>
            <div className="mt-4 space-y-4">
              <div>
                <label htmlFor="start" className="mb-2 block text-sm text-slate-300">
                  С
                </label>
                <input
                  id="start"
                  type="datetime-local"
                  value={start}
                  onChange={(e) => setStart(e.target.value)}
                  className="w-full rounded-2xl border border-white/10 bg-slate-900 px-4 py-3 text-slate-100 outline-none transition focus:border-emerald-300"
                />
              </div>
              <div>
                <label htmlFor="end" className="mb-2 block text-sm text-slate-300">
                  По
                </label>
                <input
                  id="end"
                  type="datetime-local"
                  value={end}
                  onChange={(e) => setEnd(e.target.value)}
                  className="w-full rounded-2xl border border-white/10 bg-slate-900 px-4 py-3 text-slate-100 outline-none transition focus:border-emerald-300"
                />
              </div>
              <button
                type="submit"
                className="w-full rounded-2xl bg-emerald-400 px-4 py-3 font-medium text-slate-950 transition hover:bg-emerald-300"
              >
                Обновить
              </button>
            </div>
          </form>
        </div>

        <section className="mt-8 grid gap-6 md:grid-cols-2">
          <article className="rounded-3xl border border-cyan-400/20 bg-cyan-400/10 p-8 shadow-2xl shadow-cyan-950/10">
            <p className="text-sm uppercase tracking-[0.28em] text-cyan-200">Звонки</p>
            <p className="mt-5 text-5xl font-semibold text-white">{stats?.call_count ?? 0}</p>
            <p className="mt-3 text-sm text-slate-300">Количество завершенных звонков за выбранный период.</p>
          </article>

          <article className="rounded-3xl border border-emerald-400/20 bg-emerald-400/10 p-8 shadow-2xl shadow-emerald-950/10">
            <p className="text-sm uppercase tracking-[0.28em] text-emerald-200">Общее время</p>
            <p className="mt-5 text-5xl font-semibold text-white">{stats?.total_time ?? "0"}</p>
            <p className="mt-3 text-sm text-slate-300">Суммарная длительность разговоров менеджера.</p>
          </article>
        </section>
      </main>
    </div>
  );
}
