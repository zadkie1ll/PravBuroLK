import { FormEvent, useEffect, useState } from "react";
import { DestinationStat, api } from "../api/client";

/** Легаси-статистика (порт urlshorter/templates/url-stats.html), переоформлена в единый
 * светлый стиль сервиса — функционал не менялся, только визуал. */

const REDIRECT_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8011";

const inputClass =
  "rounded-lg border border-gray-300 px-3 py-1.5 text-sm text-[#1c1c1e] focus:border-gray-500 focus:outline-none focus:ring-1 focus:ring-gray-500";
const primaryBtn = "rounded-lg bg-[#1c1c1e] px-4 py-1.5 text-sm font-medium text-white transition hover:bg-[#333]";
const dangerBtn = "rounded-lg bg-red-50 px-3 py-1.5 text-sm font-medium text-red-600 transition hover:bg-red-100";

type Notice = { kind: "success" | "error"; text: string };

const PAGE_SIZE = 10;

export function StatsPage() {
  const [stats, setStats] = useState<DestinationStat[]>([]);
  const [page, setPage] = useState(1);
  const [notice, setNotice] = useState<Notice | null>(null);
  const [newDestination, setNewDestination] = useState({ destination: "", source: "" });
  const [addSourceFor, setAddSourceFor] = useState<string | null>(null);
  const [newSource, setNewSource] = useState("");
  const [editDestination, setEditDestination] = useState<Record<string, string>>({});
  const [editSourceForm, setEditSourceForm] = useState<Record<string, { source: string; destination: string }>>({});

  async function load() {
    try {
      const result = await api.stats();
      setStats(result.stats);
    } catch (e) {
      setNotice({ kind: "error", text: e instanceof Error ? e.message : "Ошибка запроса" });
    }
  }

  useEffect(() => {
    load();
  }, []);

  useEffect(() => {
    const maxPage = Math.max(1, Math.ceil(stats.length / PAGE_SIZE));
    if (page > maxPage) setPage(maxPage);
  }, [stats, page]);

  function report(promise: Promise<{ message: string }>) {
    promise
      .then((result) => {
        setNotice({ kind: "success", text: result.message });
        load();
      })
      .catch((e) => setNotice({ kind: "error", text: e instanceof Error ? e.message : "Ошибка" }));
  }

  function addDestination(e: FormEvent) {
    e.preventDefault();
    report(api.createSource({ source: newDestination.source, destination: newDestination.destination }));
    setNewDestination({ destination: "", source: "" });
  }

  function addSource(e: FormEvent, destination: string) {
    e.preventDefault();
    report(api.createSource({ source: newSource, destination }));
    setNewSource("");
    setAddSourceFor(null);
  }

  function saveDestination(e: FormEvent, oldDestination: string) {
    e.preventDefault();
    const value = editDestination[oldDestination] ?? oldDestination;
    report(api.updateDestination({ old_destination: oldDestination, new_destination: value }));
  }

  function deleteDestination(destination: string) {
    if (!confirm(`Удалить назначение ${destination} и ВСЕ источники внутри? Это действие нельзя отменить!`)) return;
    report(api.deleteDestination(destination));
  }

  function saveSource(e: FormEvent, oldSource: string) {
    e.preventDefault();
    const form = editSourceForm[oldSource];
    if (!form) return;
    report(api.updateSource(oldSource, { new_source: form.source, new_destination: form.destination }));
  }

  function deleteSource(source: string) {
    if (!confirm(`Удалить источник ${source}?`)) return;
    report(api.deleteSource(source));
  }

  function copyLink(source: string) {
    const link = `${REDIRECT_BASE_URL}/url?source=${encodeURIComponent(source)}`;
    navigator.clipboard
      .writeText(link)
      .then(() => alert(`Ссылка скопирована:\n${link}`))
      .catch(() => alert("Не удалось скопировать"));
  }

  return (
    <div className="space-y-6">
      <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
        <h2 className="mb-3 text-sm font-semibold">Добавить новое назначение</h2>
        <form onSubmit={addDestination} className="flex flex-wrap items-center gap-2">
          <input
            type="url"
            required
            placeholder="URL назначения (https://...)"
            value={newDestination.destination}
            onChange={(e) => setNewDestination({ ...newDestination, destination: e.target.value })}
            className={`${inputClass} w-96`}
          />
          <input
            type="text"
            required
            placeholder="Код источника (tgchat)"
            value={newDestination.source}
            onChange={(e) => setNewDestination({ ...newDestination, source: e.target.value })}
            className={inputClass}
          />
          <button type="submit" className={primaryBtn}>
            Добавить
          </button>
        </form>
      </div>

      {notice && (
        <p className={`text-center text-sm font-medium ${notice.kind === "success" ? "text-green-600" : "text-red-600"}`}>
          {notice.text}
        </p>
      )}

      {stats.length === 0 && <p className="text-center text-sm text-gray-400">Нет назначений для отображения. Добавьте первое!</p>}

      {stats.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE).map((item) => (
        <div key={item.destination} className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
          <div className="mb-1 break-all text-sm font-semibold text-[#1c1c1e]">{item.destination}</div>
          <p className="mb-3 text-sm text-gray-500">
            Всего кликов: <strong className="text-[#1c1c1e]">{item.total_clicks}</strong>
          </p>

          <form onSubmit={(e) => saveDestination(e, item.destination)} className="mb-3 flex flex-wrap items-center gap-2">
            <input
              type="url"
              required
              value={editDestination[item.destination] ?? item.destination}
              onChange={(e) => setEditDestination({ ...editDestination, [item.destination]: e.target.value })}
              className={`${inputClass} w-[500px]`}
            />
            <button type="submit" className={primaryBtn}>
              Изменить URL назначения
            </button>
          </form>

          <div className="mb-4 flex flex-wrap items-center gap-2">
            <button type="button" onClick={() => deleteDestination(item.destination)} className={dangerBtn}>
              Удалить назначение целиком
            </button>

            {addSourceFor === item.destination ? (
              <form onSubmit={(e) => addSource(e, item.destination)} className="flex items-center gap-2">
                <input
                  type="text"
                  required
                  autoFocus
                  placeholder="Новый код источника"
                  value={newSource}
                  onChange={(e) => setNewSource(e.target.value)}
                  className={inputClass}
                />
                <button type="submit" className={primaryBtn}>
                  Добавить источник
                </button>
              </form>
            ) : (
              <button type="button" onClick={() => setAddSourceFor(item.destination)} className={primaryBtn}>
                Добавить источник
              </button>
            )}
          </div>

          <div className="overflow-hidden rounded-lg border border-gray-100">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">
                  <th className="px-3 py-2">Источник</th>
                  <th className="px-3 py-2">Клики</th>
                  <th className="px-3 py-2">Ссылка</th>
                  <th className="px-3 py-2">Изменить / Удалить</th>
                </tr>
              </thead>
              <tbody>
                {item.sources.map((src) => {
                  const edit = editSourceForm[src.source] ?? { source: src.source, destination: item.destination };
                  return (
                    <tr key={src.source} className="border-t border-gray-100 hover:bg-gray-50">
                      <td className="px-3 py-2">{src.source}</td>
                      <td className="px-3 py-2">{src.clicks}</td>
                      <td className="px-3 py-2">
                        <button
                          type="button"
                          onClick={() => copyLink(src.source)}
                          className="rounded-md bg-gray-100 px-3 py-1 text-xs font-medium text-gray-700 hover:bg-gray-200"
                        >
                          Копировать
                        </button>
                      </td>
                      <td className="px-3 py-2">
                        <div className="flex flex-wrap items-center gap-2">
                          <form onSubmit={(e) => saveSource(e, src.source)} className="flex items-center gap-2">
                            <input
                              type="text"
                              size={15}
                              value={edit.source}
                              onChange={(e) =>
                                setEditSourceForm({
                                  ...editSourceForm,
                                  [src.source]: { ...edit, source: e.target.value },
                                })
                              }
                              className={`${inputClass} px-2 py-1`}
                            />
                            <button type="submit" className="rounded-md bg-gray-100 px-3 py-1 text-xs font-medium text-gray-700 hover:bg-gray-200">
                              Сохранить
                            </button>
                          </form>
                          <button type="button" onClick={() => deleteSource(src.source)} className={dangerBtn}>
                            Удалить
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
                {item.sources.length === 0 && (
                  <tr>
                    <td colSpan={4} className="px-3 py-2 text-gray-400">
                      Источников нет (странно, но бывает)
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      ))}

      {stats.length > PAGE_SIZE && (
        <div className="flex items-center justify-center gap-4 rounded-xl border border-gray-200 bg-white px-4 py-3 shadow-sm">
          <button
            disabled={page <= 1}
            onClick={() => setPage((p) => p - 1)}
            className="rounded-md px-3 py-1.5 text-sm font-medium text-gray-600 hover:bg-gray-100 disabled:opacity-30"
          >
            ← Назад
          </button>
          <span className="text-sm text-gray-500">
            Страница {page} из {Math.ceil(stats.length / PAGE_SIZE)}
          </span>
          <button
            disabled={page >= Math.ceil(stats.length / PAGE_SIZE)}
            onClick={() => setPage((p) => p + 1)}
            className="rounded-md px-3 py-1.5 text-sm font-medium text-gray-600 hover:bg-gray-100 disabled:opacity-30"
          >
            Вперёд →
          </button>
        </div>
      )}
    </div>
  );
}
