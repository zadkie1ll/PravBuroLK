import { FormEvent, Fragment, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { WithdrawalRecordOut, WithdrawalsPageResponse, api } from "../api/client";

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

const inputClass =
  "w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-[#1c1c1e] focus:border-gray-500 focus:outline-none focus:ring-1 focus:ring-gray-500";
const labelClass = "mb-1 block text-xs font-semibold uppercase tracking-wide text-gray-500";
const primaryBtn = "rounded-lg bg-[#1c1c1e] px-5 py-2 text-sm font-medium text-white transition hover:bg-[#333]";
const thClass = "px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500";

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
      <div className="mx-auto max-w-3xl bg-[#f7f7f8] py-10 text-center">
        <p className="mb-4 text-sm text-red-600">{error}</p>
        <Link to="/" className="text-sm font-medium text-[#1c1c1e] underline">
          ← Назад к поиску клиентов
        </Link>
      </div>
    );
  }

  if (!data) return null;

  const { client, records, total_withdrawal_amount, total_tail_amount } = data;
  const tailIsPositive = Number(total_tail_amount) > 0;

  return (
    <div className="min-h-screen bg-[#f7f7f8]">
      <div className="mx-auto max-w-6xl px-6 py-8">
        <header className="mb-6 flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
          <div>
            <h1 className="text-lg font-semibold text-[#1c1c1e]">Списания клиента</h1>
            <p className="mt-1 text-sm text-gray-500">
              {client.surname} {client.name} {client.middlename}
            </p>
          </div>

          <div className="flex items-center gap-2">
            <Link
              to={`/clients/${client.id}`}
              className="rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-[#1c1c1e] transition hover:bg-gray-50"
            >
              К карточке клиента
            </Link>
            <Link to="/" className={primaryBtn}>
              К поиску
            </Link>
          </div>
        </header>

        {notice && (
          <div
            className={`mb-6 rounded-lg border px-4 py-3 text-sm ${
              notice.kind === "success" ? "border-green-200 bg-green-50 text-green-700" : "border-amber-200 bg-amber-50 text-amber-800"
            }`}
          >
            {notice.text}
          </div>
        )}

        <div className="mb-6 rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
          <h2 className="mb-4 text-base font-semibold text-[#1c1c1e]">Новая запись списания</h2>
          <form onSubmit={addRecord} className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-5">
            <div>
              <label className={labelClass}>Дата снятия</label>
              <input
                type="date"
                value={newRecord.withdrawal_date}
                onChange={(e) => setNewRecord({ ...newRecord, withdrawal_date: e.target.value })}
                className={inputClass}
              />
            </div>
            <div>
              <label className={labelClass}>Сумма снятия</label>
              <input
                type="number"
                step="0.01"
                min={0}
                value={newRecord.withdrawal_amount}
                onChange={(e) => setNewRecord({ ...newRecord, withdrawal_amount: e.target.value })}
                className={inputClass}
              />
            </div>
            <div>
              <label className={labelClass}>Дата перевода</label>
              <input
                type="date"
                value={newRecord.transfer_date}
                onChange={(e) => setNewRecord({ ...newRecord, transfer_date: e.target.value })}
                className={inputClass}
              />
            </div>
            <div>
              <label className={labelClass}>Сумма перевода</label>
              <input
                type="number"
                step="0.01"
                min={0}
                value={newRecord.transferred_amount}
                onChange={(e) => setNewRecord({ ...newRecord, transferred_amount: e.target.value })}
                className={inputClass}
              />
            </div>
            <div className="flex items-end">
              <button type="submit" className={`${primaryBtn} w-full`}>
                Сохранить запись
              </button>
            </div>
            <div className="xl:col-span-5">
              <label className={labelClass}>Комментарий</label>
              <input
                type="text"
                maxLength={255}
                placeholder="Добавьте комментарий (необязательно)"
                value={newRecord.comment}
                onChange={(e) => setNewRecord({ ...newRecord, comment: e.target.value })}
                className={inputClass}
              />
            </div>
          </form>
        </div>

        <div className="overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-gray-100 px-6 py-4">
            <div className="flex items-center gap-3">
              <h2 className="text-base font-semibold text-[#1c1c1e]">История списаний</h2>
              <span className="rounded-full bg-gray-100 px-3 py-1 text-xs font-medium text-gray-600">
                {records.length} записей
              </span>
            </div>
            {records.length > 0 && (
              <div className="space-y-0.5 text-right text-sm text-gray-500">
                <p>
                  Итого снято: <span className="font-semibold text-[#1c1c1e]">{total_withdrawal_amount} ₽</span>
                </p>
                <p>
                  Общий хвост:{" "}
                  <span className={`font-semibold ${tailIsPositive ? "text-amber-600" : "text-green-600"}`}>
                    {total_tail_amount} ₽
                  </span>
                </p>
              </div>
            )}
          </div>

          {records.length === 0 ? (
            <div className="px-6 py-16 text-center">
              <p className="text-sm text-gray-500">Записей списаний пока нет</p>
              <p className="mt-1 text-sm text-gray-400">Добавьте первую запись выше</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50">
                    <th className={thClass}>Дата снятия</th>
                    <th className={thClass}>Сумма снятия</th>
                    <th className={thClass}>Дата перевода</th>
                    <th className={thClass}>Сумма перевода</th>
                    <th className={thClass}>Хвост</th>
                    <th className={thClass}>Комментарий</th>
                    <th className={`${thClass} text-right`}>Действия</th>
                  </tr>
                </thead>
                <tbody>
                  {records.map((record) => (
                    <Fragment key={record.id}>
                      <tr className="border-t border-gray-100 hover:bg-gray-50">
                        <td className="px-4 py-3 font-medium text-[#1c1c1e]">
                          {record.withdrawal_date ? record.withdrawal_date : <span className="text-gray-400">—</span>}
                        </td>
                        <td className="px-4 py-3 font-medium text-[#1c1c1e]">
                          {record.withdrawal_amount ? `${record.withdrawal_amount} ₽` : <span className="text-gray-400">—</span>}
                        </td>
                        <td className="px-4 py-3 text-gray-600">
                          {record.transfer_date ? record.transfer_date : <span className="text-gray-400">—</span>}
                        </td>
                        <td className="px-4 py-3 font-medium text-[#1c1c1e]">
                          {record.transferred_amount ? `${record.transferred_amount} ₽` : <span className="text-gray-400">—</span>}
                        </td>
                        <td className={`px-4 py-3 font-semibold ${Number(record.tail_amount) > 0 ? "text-amber-600" : "text-green-600"}`}>
                          {record.tail_amount} ₽
                        </td>
                        <td className="max-w-xs truncate px-4 py-3 text-gray-600">{record.comment || "—"}</td>
                        <td className="px-4 py-3">
                          <div className="flex items-center justify-end gap-1">
                            <button
                              type="button"
                              onClick={() => startEdit(record)}
                              className="rounded-md px-3 py-1.5 text-xs font-medium text-gray-600 transition hover:bg-gray-100"
                            >
                              Редактировать
                            </button>
                            <button
                              type="button"
                              onClick={() => setDeleteTarget(record.id)}
                              className="rounded-md px-3 py-1.5 text-xs font-medium text-red-600 transition hover:bg-red-50"
                            >
                              Удалить
                            </button>
                          </div>
                        </td>
                      </tr>
                      {editingId === record.id && (
                        <tr className="border-t border-gray-100 bg-[#f7f7f8]">
                          <td colSpan={7} className="px-6 py-5">
                            <form onSubmit={(e) => saveEdit(e, record.id)} className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-5">
                              <div>
                                <label className={labelClass}>Дата снятия</label>
                                <input
                                  type="date"
                                  value={editForm.withdrawal_date}
                                  onChange={(e) => setEditForm({ ...editForm, withdrawal_date: e.target.value })}
                                  className={inputClass}
                                />
                              </div>
                              <div>
                                <label className={labelClass}>Сумма снятия</label>
                                <input
                                  type="number"
                                  step="0.01"
                                  min={0}
                                  value={editForm.withdrawal_amount}
                                  onChange={(e) => setEditForm({ ...editForm, withdrawal_amount: e.target.value })}
                                  className={inputClass}
                                />
                              </div>
                              <div>
                                <label className={labelClass}>Дата перевода</label>
                                <input
                                  type="date"
                                  value={editForm.transfer_date}
                                  onChange={(e) => setEditForm({ ...editForm, transfer_date: e.target.value })}
                                  className={inputClass}
                                />
                              </div>
                              <div>
                                <label className={labelClass}>Сумма перевода</label>
                                <input
                                  type="number"
                                  step="0.01"
                                  min={0}
                                  value={editForm.transferred_amount}
                                  onChange={(e) => setEditForm({ ...editForm, transferred_amount: e.target.value })}
                                  className={inputClass}
                                />
                              </div>
                              <div className="flex items-end gap-2">
                                <button type="submit" className={`${primaryBtn} flex-1`}>
                                  Сохранить
                                </button>
                                <button
                                  type="button"
                                  onClick={() => setEditingId(null)}
                                  className="rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-600 transition hover:bg-gray-50"
                                >
                                  ✕
                                </button>
                              </div>
                              <div className="xl:col-span-5">
                                <label className={labelClass}>Комментарий</label>
                                <input
                                  type="text"
                                  maxLength={255}
                                  value={editForm.comment}
                                  onChange={(e) => setEditForm({ ...editForm, comment: e.target.value })}
                                  className={inputClass}
                                />
                              </div>
                            </form>
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {deleteTarget !== null && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="w-full max-w-md space-y-4 rounded-xl border border-gray-200 bg-white p-6 shadow-xl">
            <h3 className="text-base font-semibold text-[#1c1c1e]">Удалить запись?</h3>
            <p className="text-sm text-gray-500">Вы уверены, что хотите удалить эту запись? Это действие необратимо.</p>
            <div className="flex justify-end gap-3">
              <button
                onClick={() => setDeleteTarget(null)}
                className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-[#1c1c1e] hover:bg-gray-50"
              >
                Отмена
              </button>
              <button
                onClick={confirmDelete}
                className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700"
              >
                Удалить
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
