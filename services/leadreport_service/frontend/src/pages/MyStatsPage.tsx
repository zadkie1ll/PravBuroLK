import { FormEvent, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, clearToken, ManagerStats } from "../api/client";

function toLocalInput(iso: string): string {
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function MyStatsPage() {
  const [stats, setStats] = useState<ManagerStats | null>(null);
  const [error, setError] = useState("");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const navigate = useNavigate();

  function load(s?: string, e?: string) {
    setError("");
    api
      .myStats(s, e)
      .then((res) => {
        setStats(res);
        setStart(toLocalInput(res.period_start));
        setEnd(toLocalInput(res.period_end));
      })
      .catch((err) => setError(err.message));
  }

  useEffect(() => load(), []); // eslint-disable-line react-hooks/exhaustive-deps

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    load(start, end);
  }

  function logout() {
    clearToken();
    navigate("/login");
  }

  return (
    <div className="relative min-h-screen bg-stone-950 text-stone-100">
      <div className="pointer-events-none fixed inset-0 -z-10 bg-[radial-gradient(circle_at_top_right,_rgba(251,191,36,0.14),_transparent_24%),radial-gradient(circle_at_top_left,_rgba(249,115,22,0.12),_transparent_24%),linear-gradient(180deg,_#1c1917_0%,_#0c0a09_100%)]" />

      <main className="mx-auto max-w-6xl px-6 py-10">
        <div className="mb-4 flex justify-end">
          <button onClick={logout} className="text-sm text-amber-300 hover:underline">
            Выйти
          </button>
        </div>

        {error && (
          <div className="mb-6 rounded-2xl border border-red-400/30 bg-red-400/10 p-4 text-red-200">{error}</div>
        )}

        <section className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
          <div className="rounded-3xl border border-white/10 bg-white/5 p-8 shadow-2xl shadow-amber-950/20 backdrop-blur">
            <p className="text-xs uppercase tracking-[0.35em] text-amber-300">Lead Report</p>
            <h1 className="mt-3 text-3xl font-semibold text-white">Моя статистика</h1>
            {stats && (
              <>
                <h2 className="mt-5 text-xl text-amber-100">{stats.manager.name}</h2>
                <p className="mt-2 text-stone-300">Bitrix ID: {stats.manager.bitrix_user_id}</p>
                {stats.manager.email && <p className="mt-1 text-stone-400">{stats.manager.email}</p>}
                {stats.manager.phone && <p className="mt-1 text-stone-400">{stats.manager.phone}</p>}
              </>
            )}
          </div>

          <form onSubmit={handleSubmit} className="rounded-3xl border border-amber-400/20 bg-amber-400/10 p-8 shadow-2xl shadow-amber-950/20">
            <p className="text-sm uppercase tracking-[0.28em] text-amber-200">Период отчета</p>
            <div className="mt-5 space-y-4">
              <div>
                <label htmlFor="start" className="mb-2 block text-sm text-stone-200">
                  С
                </label>
                <input
                  id="start"
                  type="datetime-local"
                  value={start}
                  onChange={(e) => setStart(e.target.value)}
                  className="w-full rounded-2xl border border-white/10 bg-stone-950/70 px-4 py-3 text-stone-100 outline-none transition focus:border-amber-300"
                />
              </div>
              <div>
                <label htmlFor="end" className="mb-2 block text-sm text-stone-200">
                  По
                </label>
                <input
                  id="end"
                  type="datetime-local"
                  value={end}
                  onChange={(e) => setEnd(e.target.value)}
                  className="w-full rounded-2xl border border-white/10 bg-stone-950/70 px-4 py-3 text-stone-100 outline-none transition focus:border-amber-300"
                />
              </div>
              <button
                type="submit"
                className="w-full rounded-2xl bg-white px-4 py-3 font-medium text-stone-950 transition hover:bg-amber-100"
              >
                Обновить статистику
              </button>
            </div>
          </form>
        </section>

        <section className="mt-8 grid gap-6 md:grid-cols-2">
          <article className="rounded-3xl border border-white/10 bg-white/5 p-8">
            <p className="text-sm uppercase tracking-[0.25em] text-stone-400">Звонки</p>
            <p className="mt-4 text-5xl font-semibold text-white">{stats?.call_count ?? 0}</p>
          </article>
          <article className="rounded-3xl border border-white/10 bg-white/5 p-8">
            <p className="text-sm uppercase tracking-[0.25em] text-stone-400">Общее время</p>
            <p className="mt-4 text-5xl font-semibold text-white">{stats?.total_time ?? "0"}</p>
          </article>
        </section>

        <section className="mt-8 rounded-3xl border border-dashed border-amber-400/30 bg-amber-400/5 p-6 text-stone-300">
          Скоро здесь можно будет добавить лиды, конверсию и более детальную аналитику по дням.
        </section>
      </main>
    </div>
  );
}
