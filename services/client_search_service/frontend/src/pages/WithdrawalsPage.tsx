import { FormEvent, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { WithdrawalRecordOut, WithdrawalsPageResponse, api } from "../api/client";

/** Порт client_withdrawals/templates/client_withdrawals/client_withdrawals_page.html —
 * тот же светлый "glass" стиль (rounded-3xl, backdrop-blur, emerald-акцент), третий
 * отдельный визуальный язык в проекте, не путать с тёмной glassmorphism leadreport
 * или plain-light admin-hub. См. UI-parity lesson в памяти проекта: читать реальный
 * шаблон, а не переиспользовать чужой стиль. */

type EmptyForm = {
  withdrawal_date: string;
  transfer_date: string;
  withdrawal_amount: string;
  transferred_amount: string;
  comment: string;
};

const EMPTY_FORM: EmptyForm = {
  withdrawal_date: "",
  transfer_date: "",
  withdrawal_amount: "",
  transferred_amount: "",
  comment: "",
};

export function WithdrawalsPage() {
  const { clientId } = useParams<{ clientId: string }>();
  const id = Number(clientId);

  const [data, setData] = useState<WithdrawalsPageResponse | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState<{ kind: "success" | "warning"; text: string } | null>(null);
  const [newRecord, setNewRecord] = useState<EmptyForm>(EMPTY_FORM);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editForm, setEditForm] = useState<EmptyForm>(EMPTY_FORM);
  const [deleteTarget, setDeleteTarget] = useState<number | null>(null);

  async function load() {
    try {
      const page = await api.withdrawalsPage(id);
      setData(page);
      setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка запроса");
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  function applyMutationResult(result: { bitrix_warning: string | null }, successText: string) {
    if (result.bitrix_warning) {
      setNotice({ kind: "warning", text: `${successText}, но Битрикс не обновлен: ${result.bitrix_warning}` });
    } else {
      setNotice({ kind: "success", text: `${successText} и синхронизировано с Битрикс.` });
    }
  }

  async function addRecord(e: FormEvent) {
    e.preventDefault();
    try {
      const result = await api.createWithdrawal(id, {
        withdrawal_date: newRecord.withdrawal_date || null,
        transfer_date: newRecord.transfer_date || null,
        withdrawal_amount: newRecord.withdrawal_amount || null,
        transferred_amount: newRecord.transferred_amount || null,
        comment: newRecord.comment,
      });
      setNewRecord(EMPTY_FORM);
      applyMutationResult(result, "Запись добавлена");
      await load();
    } catch (e) {
      alert(e instanceof Error ? e.message : "Не удалось сохранить запись");
    }
  }

  function startEdit(record: WithdrawalRecordOut) {
    setEditingId((current) => (current === record.id ? null : record.id));
    setEditForm({
      withdrawal_date: record.withdrawal_date || "",
      transfer_date: record.transfer_date || "",
      withdrawal_amount: record.withdrawal_amount || "",
      transferred_amount: record.transferred_amount || "",
      comment: record.comment,
    });
  }

  async function saveEdit(e: FormEvent, recordId: number) {
    e.preventDefault();
    try {
      const result = await api.updateWithdrawal(recordId, {
        withdrawal_date: editForm.withdrawal_date || null,
        transfer_date: editForm.transfer_date || null,
        withdrawal_amount: editForm.withdrawal_amount || null,
        transferred_amount: editForm.transferred_amount || null,
        comment: editForm.comment,
      });
      setEditingId(null);
      applyMutationResult(result, "Запись обновлена");
      await load();
    } catch (e) {
      alert(e instanceof Error ? e.message : "Не удалось обновить запись");
    }
  }

  async function confirmDelete() {
    if (deleteTarget === null) return;
    try {
      const result = await api.deleteWithdrawal(deleteTarget);
      setDeleteTarget(null);
      applyMutationResult(result, "Запись удалена");
      await load();
    } catch {
      setDeleteTarget(null);
      alert("Не удалось удалить запись");
    }
  }

  if (error) {
    return (
      <div className="mx-auto max-w-3xl py-10 text-center">
        <p className="mb-4 text-red-600">{error}</p>
        <Link to="/" className="text-blue-600 underline">
          ← Назад к поиску клиентов
        </Link>
      </div>
    );
  }

  if (!data) return null;

  const { client, records, total_withdrawal_amount, total_tail_amount } = data;
  const tailIsPositive = Number(total_tail_amount) > 0;

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 text-slate-900">
      <div className="mx-auto max-w-7xl px-6 py-8">
        <header className="mb-10 flex flex-col justify-between gap-6 sm:flex-row sm:items-center">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-emerald-100 text-2xl text-emerald-600">
              ↘
            </div>
            <div>
              <h1 className="text-4xl font-semibold tracking-tight">Списания клиента</h1>
              <p className="mt-1 text-lg text-slate-600">
                {client.surname} {client.name} {client.middlename}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <Link
              to={`/clients/${client.id}`}
              className="flex items-center gap-2 rounded-2xl border border-slate-200 bg-white px-6 py-3 text-slate-700 transition-all duration-200 hover:border-slate-300 hover:shadow-sm"
            >
              К карточке клиента
            </Link>
            <Link
              to="/"
              className="flex items-center gap-2 rounded-2xl bg-slate-900 px-6 py-3 text-white transition-all duration-200 hover:bg-slate-800"
            >
              К поиску
            </Link>
          </div>
        </header>

        {notice && (
          <div className="mb-8 space-y-3">
            <div
              className={`flex items-center gap-3 rounded-3xl border px-6 py-4 shadow-sm backdrop-blur-xl ${
                notice.kind === "success"
                  ? "border-emerald-200 bg-white/95 text-slate-700"
                  : "border-amber-300 bg-amber-50/95 text-amber-800"
              }`}
            >
              <p>{notice.text}</p>
            </div>
          </div>
        )}

        <div className="mb-10 overflow-hidden rounded-3xl border border-slate-100 bg-white/95 shadow-xl backdrop-blur-xl">
          <div className="border-b border-slate-100 px-8 pb-6 pt-8">
            <h2 className="flex items-center gap-3 text-2xl font-semibold">Новая запись списания</h2>
          </div>
          <form onSubmit={addRecord} className="grid grid-cols-1 gap-6 p-8 md:grid-cols-2 xl:grid-cols-5">
            <div className="space-y-2">
              <label className="block text-sm font-medium text-slate-600">Дата снятия</label>
              <input
                type="date"
                value={newRecord.withdrawal_date}
                onChange={(e) => setNewRecord({ ...newRecord, withdrawal_date: e.target.value })}
                className="w-full rounded-2xl border border-slate-200 bg-white px-5 py-4 focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-200"
              />
            </div>
            <div className="space-y-2">
              <label className="block text-sm font-medium text-slate-600">Сумма снятия</label>
              <input
                type="number"
                step="0.01"
                min={0}
                value={newRecord.withdrawal_amount}
                onChange={(e) => setNewRecord({ ...newRecord, withdrawal_amount: e.target.value })}
                className="w-full rounded-2xl border border-slate-200 bg-white px-5 py-4 focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-200"
              />
            </div>
            <div className="space-y-2">
              <label className="block text-sm font-medium text-slate-600">Дата перевода</label>
              <input
                type="date"
                value={newRecord.transfer_date}
                onChange={(e) => setNewRecord({ ...newRecord, transfer_date: e.target.value })}
                className="w-full rounded-2xl border border-slate-200 bg-white px-5 py-4 focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-200"
              />
            </div>
            <div className="space-y-2">
              <label className="block text-sm font-medium text-slate-600">Сумма перевода</label>
              <input
                type="number"
                step="0.01"
                min={0}
                value={newRecord.transferred_amount}
                onChange={(e) => setNewRecord({ ...newRecord, transferred_amount: e.target.value })}
                className="w-full rounded-2xl border border-slate-200 bg-white px-5 py-4 focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-200"
              />
            </div>
            <div className="flex items-end">
              <button
                type="submit"
                className="flex w-full items-center justify-center gap-2 rounded-2xl bg-emerald-600 py-4 font-semibold text-white shadow-lg shadow-emerald-500/30 transition-all duration-200 hover:bg-emerald-700"
              >
                Сохранить запись
              </button>
            </div>
            <div className="space-y-2 xl:col-span-5">
              <label className="block text-sm font-medium text-slate-600">Комментарий</label>
              <input
                type="text"
                maxLength={255}
                placeholder="Добавьте комментарий (необязательно)"
                value={newRecord.comment}
                onChange={(e) => setNewRecord({ ...newRecord, comment: e.target.value })}
                className="w-full rounded-2xl border border-slate-200 bg-white px-5 py-4 focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-200"
              />
            </div>
          </form>
        </div>

        <div className="overflow-hidden rounded-3xl border border-slate-100 bg-white/95 shadow-xl backdrop-blur-xl">
          <div className="flex items-center justify-between border-b border-slate-100 px-8 py-6">
            <div className="flex items-center gap-4">
              <h2 className="text-2xl font-semibold">История списаний</h2>
              <span className="rounded-2xl bg-slate-100 px-4 py-1.5 text-sm font-medium text-slate-600">
                {records.length} записей
              </span>
            </div>
            {records.length > 0 && (
              <div className="space-y-1 text-right text-sm text-slate-500">
                <p>
                  Итого снято: <span className="font-semibold text-slate-700">{total_withdrawal_amount} ₽</span>
                </p>
                <p>
                  Общий хвост:{" "}
                  <span className={`font-semibold ${tailIsPositive ? "text-amber-600" : "text-emerald-600"}`}>
                    {total_tail_amount} ₽
                  </span>
                </p>
              </div>
            )}
          </div>

          {records.length === 0 ? (
            <div className="px-8 py-20 text-center">
              <p className="text-lg text-slate-500">Записей списаний пока нет</p>
              <p className="mt-1 text-slate-400">Добавьте первую запись выше</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-50">
                    <th className="px-8 py-5 text-left font-medium text-slate-500">Дата снятия</th>
                    <th className="px-8 py-5 text-left font-medium text-slate-500">Сумма снятия</th>
                    <th className="px-8 py-5 text-left font-medium text-slate-500">Дата перевода</th>
                    <th className="px-8 py-5 text-left font-medium text-slate-500">Сумма перевода</th>
                    <th className="px-8 py-5 text-left font-medium text-slate-500">Хвост</th>
                    <th className="px-8 py-5 text-left font-medium text-slate-500">Комментарий</th>
                    <th className="px-8 py-5 text-right font-medium text-slate-500">Действия</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {records.map((record) => (
                    <>
                      <tr key={record.id} className="group transition-transform duration-200 hover:translate-x-1 hover:bg-slate-50">
                        <td className="px-8 py-5 font-medium">
                          {record.withdrawal_date ? record.withdrawal_date : <span className="text-slate-400">—</span>}
                        </td>
                        <td className="px-8 py-5 font-semibold text-slate-900">
                          {record.withdrawal_amount ? `${record.withdrawal_amount} ₽` : <span className="text-slate-400">—</span>}
                        </td>
                        <td className="px-8 py-5 text-slate-600">
                          {record.transfer_date ? record.transfer_date : <span className="text-slate-400">—</span>}
                        </td>
                        <td className="px-8 py-5 font-semibold text-slate-900">
                          {record.transferred_amount ? `${record.transferred_amount} ₽` : <span className="text-slate-400">—</span>}
                        </td>
                        <td
                          className={`px-8 py-5 text-lg font-bold ${
                            Number(record.tail_amount) > 0 ? "text-amber-600" : "text-emerald-600"
                          }`}
                        >
                          {record.tail_amount} ₽
                        </td>
                        <td className="max-w-xs truncate px-8 py-5 text-slate-600">{record.comment || "—"}</td>
                        <td className="px-8 py-5">
                          <div className="flex items-center justify-end gap-2 opacity-70 group-hover:opacity-100">
                            <button
                              type="button"
                              onClick={() => startEdit(record)}
                              className="rounded-2xl px-4 py-2.5 text-sm font-medium text-emerald-600 transition-all hover:bg-emerald-50 hover:text-emerald-700"
                            >
                              Редактировать
                            </button>
                            <button
                              type="button"
                              onClick={() => setDeleteTarget(record.id)}
                              className="rounded-2xl px-4 py-2.5 text-sm font-medium text-red-500 transition-all hover:bg-red-50 hover:text-red-600"
                            >
                              Удалить
                            </button>
                          </div>
                        </td>
                      </tr>
                      {editingId === record.id && (
                        <tr className="bg-emerald-50/40">
                          <td colSpan={7} className="px-8 py-6">
                            <form
                              onSubmit={(e) => saveEdit(e, record.id)}
                              className="grid grid-cols-1 gap-5 md:grid-cols-2 xl:grid-cols-5"
                            >
                              <div className="space-y-2">
                                <label className="block text-sm font-medium text-slate-600">Дата снятия</label>
                                <input
                                  type="date"
                                  value={editForm.withdrawal_date}
                                  onChange={(e) => setEditForm({ ...editForm, withdrawal_date: e.target.value })}
                                  className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-200"
                                />
                              </div>
                              <div className="space-y-2">
                                <label className="block text-sm font-medium text-slate-600">Сумма снятия</label>
                                <input
                                  type="number"
                                  step="0.01"
                                  min={0}
                                  value={editForm.withdrawal_amount}
                                  onChange={(e) => setEditForm({ ...editForm, withdrawal_amount: e.target.value })}
                                  className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-200"
                                />
                              </div>
                              <div className="space-y-2">
                                <label className="block text-sm font-medium text-slate-600">Дата перевода</label>
                                <input
                                  type="date"
                                  value={editForm.transfer_date}
                                  onChange={(e) => setEditForm({ ...editForm, transfer_date: e.target.value })}
                                  className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-200"
                                />
                              </div>
                              <div className="space-y-2">
                                <label className="block text-sm font-medium text-slate-600">Сумма перевода</label>
                                <input
                                  type="number"
                                  step="0.01"
                                  min={0}
                                  value={editForm.transferred_amount}
                                  onChange={(e) => setEditForm({ ...editForm, transferred_amount: e.target.value })}
                                  className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-200"
                                />
                              </div>
                              <div className="flex items-end gap-2">
                                <button
                                  type="submit"
                                  className="flex-1 rounded-2xl bg-emerald-600 py-3 font-semibold text-white shadow-lg shadow-emerald-500/20 transition-all duration-200 hover:bg-emerald-700"
                                >
                                  Сохранить
                                </button>
                                <button
                                  type="button"
                                  onClick={() => setEditingId(null)}
                                  className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-slate-600 transition-all hover:border-slate-300"
                                >
                                  ✕
                                </button>
                              </div>
                              <div className="space-y-2 xl:col-span-5">
                                <label className="block text-sm font-medium text-slate-600">Комментарий</label>
                                <input
                                  type="text"
                                  maxLength={255}
                                  value={editForm.comment}
                                  onChange={(e) => setEditForm({ ...editForm, comment: e.target.value })}
                                  className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-200"
                                />
                              </div>
                            </form>
                          </td>
                        </tr>
                      )}
                    </>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {deleteTarget !== null && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
          <div className="w-full max-w-md space-y-4 rounded-2xl bg-white p-6 shadow-xl">
            <h3 className="text-xl font-bold text-slate-800">Удалить запись?</h3>
            <p className="text-slate-600">Вы уверены, что хотите удалить эту запись? Это действие необратимо.</p>
            <div className="flex justify-end space-x-3">
              <button
                onClick={() => setDeleteTarget(null)}
                className="rounded-xl bg-slate-200 px-4 py-2 hover:bg-slate-300"
              >
                Отмена
              </button>
              <button onClick={confirmDelete} className="rounded-xl bg-red-600 px-4 py-2 text-white hover:bg-red-700">
                Удалить
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
