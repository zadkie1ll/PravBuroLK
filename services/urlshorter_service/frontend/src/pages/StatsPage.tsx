import { FormEvent, useEffect, useState } from "react";
import { DestinationStat, api } from "../api/client";

/** Порт urlshorter/templates/url-stats.html — простой светлый стиль (bg #f4f4f9, синий
 * акцент #007bff), четвёртый отдельный визуальный язык в проекте (не путать с glass-темой
 * client_withdrawals, dark glassmorphism leadreport или plain admin-hub). */

const REDIRECT_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8011";

type Notice = { kind: "success" | "error"; text: string };

export function StatsPage() {
  const [stats, setStats] = useState<DestinationStat[]>([]);
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
    <div className="min-h-screen bg-gray-100 p-6 text-gray-800">
      <div className="mx-auto max-w-6xl">
        <h1 className="mb-8 text-center text-3xl font-bold text-indigo-900">
          Статистика по назначениям и источникам
        </h1>

        <div className="mb-6 rounded-lg bg-white p-6 shadow">
          <h2 className="mb-4 text-xl font-semibold text-indigo-900">Добавить новое назначение</h2>
          <form onSubmit={addDestination} className="flex flex-wrap items-center gap-3">
            <input
              type="url"
              required
              placeholder="URL назначения (https://...)"
              value={newDestination.destination}
              onChange={(e) => setNewDestination({ ...newDestination, destination: e.target.value })}
              className="w-96 rounded border border-gray-300 px-3 py-2"
            />
            <input
              type="text"
              required
              placeholder="Код источника (tgchat)"
              value={newDestination.source}
              onChange={(e) => setNewDestination({ ...newDestination, source: e.target.value })}
              className="rounded border border-gray-300 px-3 py-2"
            />
            <button type="submit" className="rounded bg-blue-600 px-4 py-2 font-medium text-white hover:bg-blue-700">
              Добавить
            </button>
          </form>
        </div>

        {notice && (
          <p className={`mb-6 text-center font-bold ${notice.kind === "success" ? "text-green-600" : "text-red-600"}`}>
            {notice.text}
          </p>
        )}

        {stats.length === 0 && <p className="text-center text-gray-500">Нет назначений для отображения. Добавьте первое!</p>}

        {stats.map((item) => (
          <div key={item.destination} className="mb-6 rounded-lg bg-white p-6 shadow">
            <div className="mb-2 break-all text-lg font-semibold text-blue-600">{item.destination}</div>
            <p className="mb-4">
              Всего кликов: <strong>{item.total_clicks}</strong>
            </p>

            <form onSubmit={(e) => saveDestination(e, item.destination)} className="mb-2 flex flex-wrap items-center gap-2">
              <input
                type="url"
                required
                value={editDestination[item.destination] ?? item.destination}
                onChange={(e) => setEditDestination({ ...editDestination, [item.destination]: e.target.value })}
                className="w-[500px] rounded border border-gray-300 px-3 py-2"
              />
              <button type="submit" className="rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700">
                Изменить URL назначения
              </button>
            </form>

            <div className="mb-4 flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={() => deleteDestination(item.destination)}
                className="rounded bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700"
              >
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
                    className="rounded border border-gray-300 px-3 py-2"
                  />
                  <button type="submit" className="rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700">
                    Добавить источник
                  </button>
                </form>
              ) : (
                <button
                  type="button"
                  onClick={() => setAddSourceFor(item.destination)}
                  className="rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
                >
                  Добавить источник
                </button>
              )}
            </div>

            <table className="w-full border-collapse">
              <thead>
                <tr>
                  <th className="bg-blue-600 p-2 text-left text-white">Источник</th>
                  <th className="bg-blue-600 p-2 text-left text-white">Клики</th>
                  <th className="bg-blue-600 p-2 text-left text-white">Ссылка</th>
                  <th className="bg-blue-600 p-2 text-left text-white">Изменить / Удалить</th>
                </tr>
              </thead>
              <tbody>
                {item.sources.map((src) => {
                  const edit = editSourceForm[src.source] ?? { source: src.source, destination: item.destination };
                  return (
                    <tr key={src.source} className="border-b hover:bg-gray-50">
                      <td className="p-2">{src.source}</td>
                      <td className="p-2">{src.clicks}</td>
                      <td className="p-2">
                        <button
                          type="button"
                          onClick={() => copyLink(src.source)}
                          className="rounded bg-green-600 px-3 py-1.5 text-sm text-white hover:bg-green-700"
                        >
                          Копировать ссылку
                        </button>
                      </td>
                      <td className="p-2">
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
                              className="rounded border border-gray-300 px-2 py-1"
                            />
                            <button
                              type="submit"
                              className="rounded bg-yellow-400 px-3 py-1.5 text-sm font-medium text-black hover:bg-yellow-500"
                            >
                              Сохранить
                            </button>
                          </form>
                          <button
                            type="button"
                            onClick={() => deleteSource(src.source)}
                            className="rounded bg-red-600 px-3 py-1.5 text-sm text-white hover:bg-red-700"
                          >
                            Удалить
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
                {item.sources.length === 0 && (
                  <tr>
                    <td colSpan={4} className="p-2 text-gray-500">
                      Источников нет (странно, но бывает)
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        ))}
      </div>
    </div>
  );
}
