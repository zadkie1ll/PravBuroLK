import { FormEvent, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  ActualPaymentOut,
  ClientDetailResponse,
  InstallmentPaymentOut,
  OTHER_PAYMENT_TYPES,
  OtherPaymentOut,
  api,
} from "../api/client";

type DeleteTarget = { type: "installment" | "actual" | "other"; id: number } | null;

export function ClientDetailPage() {
  const { clientId } = useParams<{ clientId: string }>();
  const id = Number(clientId);

  const [data, setData] = useState<ClientDetailResponse | null>(null);
  const [error, setError] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<DeleteTarget>(null);

  // Локальные копии редактируемых таблиц — соответствует installments-form/actuals-form/
  // others-form в client_payments_page.html: правки копятся локально, отправляются одной
  // пачкой по кнопке "Сохранить изменения".
  const [installments, setInstallments] = useState<InstallmentPaymentOut[]>([]);
  const [actuals, setActuals] = useState<ActualPaymentOut[]>([]);
  const [others, setOthers] = useState<OtherPaymentOut[]>([]);

  const [contractForm, setContractForm] = useState({
    total_amount: "",
    discount: "",
    first_payment: "",
    first_payment_date: "",
    number_of_payments: "1",
  });

  const [newInstallment, setNewInstallment] = useState({ due_date: "", amount_due: "" });
  const [newActual, setNewActual] = useState({ payment_date: "", amount: "" });
  const [newOther, setNewOther] = useState({ payment_type: "", amount: "", comment: "" });

  async function load() {
    try {
      const detail = await api.clientDetail(id);
      setData(detail);
      setInstallments(detail.installments);
      setActuals(detail.actuals);
      setOthers(detail.other_payments);
      setContractForm({
        total_amount: detail.contract.total_amount,
        discount: detail.contract.discount,
        first_payment: detail.contract.first_payment,
        first_payment_date: detail.contract.first_payment_date,
        number_of_payments: String(detail.contract.number_of_payments),
      });
      setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка запроса");
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

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

  const { client, contract, plan_id, total_installments_sum, total_actuals_sum, contract_final_amount } = data;
  const amountsMismatch = total_installments_sum !== contract_final_amount;

  async function saveContract(e: FormEvent) {
    e.preventDefault();
    try {
      await api.updateContract(contract.id, {
        ...contractForm,
        number_of_payments: Number(contractForm.number_of_payments),
      });
      await load();
    } catch (e) {
      alert(e instanceof Error ? e.message : "Ошибка сохранения");
    }
  }

  async function addInstallment(e: FormEvent) {
    e.preventDefault();
    try {
      await api.createInstallment({ plan_id, ...newInstallment });
      setNewInstallment({ due_date: "", amount_due: "" });
      await load();
    } catch (e) {
      alert(e instanceof Error ? e.message : "Ошибка добавления");
    }
  }

  async function saveInstallments() {
    try {
      await api.bulkUpdateInstallments(
        installments.map((p) => ({ id: p.id, due_date: p.due_date, amount_due: p.amount_due, status: p.status })),
      );
      await load();
    } catch {
      alert("Ошибка при сохранении");
    }
  }

  async function addActual(e: FormEvent) {
    e.preventDefault();
    try {
      await api.createActual({ plan_id, ...newActual });
      setNewActual({ payment_date: "", amount: "" });
      await load();
    } catch (e) {
      alert(e instanceof Error ? e.message : "Ошибка добавления");
    }
  }

  async function saveActuals() {
    try {
      await api.bulkUpdateActuals(actuals.map((p) => ({ id: p.id, payment_date: p.payment_date || "", amount: p.amount })));
      await load();
    } catch {
      alert("Ошибка при сохранении");
    }
  }

  async function addOther(e: FormEvent) {
    e.preventDefault();
    try {
      await api.createOtherPayment({ client_id: client.id, ...newOther });
      setNewOther({ payment_type: "", amount: "", comment: "" });
      await load();
    } catch (e) {
      alert(e instanceof Error ? e.message : "Ошибка добавления");
    }
  }

  async function saveOthers() {
    try {
      await api.bulkUpdateOtherPayments(
        others.map((p) => ({ id: p.id, payment_type: p.payment_type, amount: p.amount, comment: p.comment })),
      );
      await load();
    } catch {
      alert("Ошибка при сохранении");
    }
  }

  async function confirmDelete() {
    if (!deleteTarget) return;
    try {
      if (deleteTarget.type === "installment") await api.deleteInstallment(deleteTarget.id);
      else if (deleteTarget.type === "actual") await api.deleteActual(deleteTarget.id);
      else await api.deleteOtherPayment(deleteTarget.id);
      setDeleteTarget(null);
      await load();
    } catch {
      alert("Ошибка при удалении");
      setDeleteTarget(null);
    }
  }

  return (
    <div className="mx-auto max-w-6xl space-y-12 px-4 py-10">
      <div className="flex flex-wrap items-center gap-3">
        <Link
          to="/"
          className="inline-block rounded-xl bg-slate-200 px-5 py-2 font-semibold text-slate-700 transition hover:bg-slate-300"
        >
          ← Назад к поиску клиентов
        </Link>
        <a
          href={data.withdrawals_url}
          className="inline-block rounded-xl bg-emerald-600 px-5 py-2 font-semibold text-white transition hover:bg-emerald-700"
        >
          Списания клиента
        </a>
        <div className="rounded-xl border border-amber-200 bg-amber-50 px-5 py-2 font-semibold text-amber-800">
          Общий хвост по снятиям: {data.total_tail_amount} ₽
        </div>
      </div>

      {client.is_blocked && (
        <div className="w-full bg-red-600 p-3 text-center font-semibold text-white">
          ⚠️ Этот клиент заблокирован.
        </div>
      )}

      <section className="rounded-2xl bg-white p-6 shadow">
        <h2 className="mb-4 text-xl font-semibold">🧑‍💼 Данные клиента</h2>
        <div className="grid grid-cols-1 gap-4 text-sm md:grid-cols-3">
          <div>
            <span className="block text-gray-500">Фамилия</span>
            <span className="block font-medium text-gray-900">{client.surname}</span>
          </div>
          <div>
            <span className="block text-gray-500">Имя</span>
            <span className="block font-medium text-gray-900">{client.name}</span>
          </div>
          <div>
            <span className="block text-gray-500">Сделка в Bitrix</span>
            {data.bitrix_deal_url ? (
              <a
                href={data.bitrix_deal_url}
                target="_blank"
                rel="noreferrer"
                className="mt-1 inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 font-medium text-white transition hover:bg-blue-700"
              >
                🔗 Открыть сделку
              </a>
            ) : (
              <span className="text-gray-400">нет bitrix_id</span>
            )}
          </div>
          <div>
            <span className="block text-gray-500">Отчество</span>
            <span className="block font-medium text-gray-900">{client.middlename}</span>
          </div>
        </div>
      </section>

      <section className="space-y-4 rounded-2xl bg-white p-6 shadow-md">
        <h2 className="text-2xl font-bold text-slate-700">Информация о контракте</h2>
        <form onSubmit={saveContract} className="space-y-4">
          <div className="grid grid-cols-1 gap-4 text-sm md:grid-cols-2">
            <div>
              <p className="mb-1 text-slate-500">Общая сумма</p>
              <input
                type="number"
                step="0.01"
                required
                value={contractForm.total_amount}
                onChange={(e) => setContractForm({ ...contractForm, total_amount: e.target.value })}
                className="w-full rounded-lg border p-2 focus:ring focus:ring-blue-300"
              />
            </div>
            <div>
              <p className="mb-1 text-slate-500">Скидка</p>
              <input
                type="number"
                step="0.01"
                required
                value={contractForm.discount}
                onChange={(e) => setContractForm({ ...contractForm, discount: e.target.value })}
                className="w-full rounded-lg border p-2 focus:ring focus:ring-blue-300"
              />
            </div>
            <div>
              <p className="mb-1 text-slate-500">Первый платеж</p>
              <input
                type="number"
                step="0.01"
                required
                value={contractForm.first_payment}
                onChange={(e) => setContractForm({ ...contractForm, first_payment: e.target.value })}
                className="w-full rounded-lg border p-2 focus:ring focus:ring-blue-300"
              />
            </div>
            <div>
              <p className="mb-1 text-slate-500">Дата первого платежа</p>
              <input
                type="date"
                required
                value={contractForm.first_payment_date}
                onChange={(e) => setContractForm({ ...contractForm, first_payment_date: e.target.value })}
                className="w-full rounded-lg border p-2 focus:ring focus:ring-blue-300"
              />
            </div>
            <div>
              <p className="mb-1 text-slate-500">Количество платежей</p>
              <input
                type="number"
                min={1}
                required
                value={contractForm.number_of_payments}
                onChange={(e) => setContractForm({ ...contractForm, number_of_payments: e.target.value })}
                className="w-full rounded-lg border p-2 focus:ring focus:ring-blue-300"
              />
            </div>
          </div>
          <button
            type="submit"
            className="rounded-lg bg-blue-600 px-6 py-2 font-semibold text-white transition hover:bg-blue-700"
          >
            Сохранить изменения
          </button>
        </form>
      </section>

      {amountsMismatch && (
        <div className="rounded-xl border border-red-300 bg-red-100 p-4 text-red-800">
          ⚠️ <b>Сумма платежей по рассрочке не совпадает с суммой по договору!</b>
          <br />
          По договору (с учётом скидки): {contract_final_amount} ₽<br />
          По рассрочке: {total_installments_sum} ₽
        </div>
      )}

      <section className="space-y-6 rounded-2xl bg-white p-6 shadow-md">
        <h2 className="text-xl font-bold text-slate-700">Платежи по плану</h2>
        <form onSubmit={addInstallment} className="flex items-center gap-4">
          <input
            type="date"
            required
            value={newInstallment.due_date}
            onChange={(e) => setNewInstallment({ ...newInstallment, due_date: e.target.value })}
            className="rounded-lg border px-3 py-2"
          />
          <input
            type="number"
            required
            placeholder="Сумма"
            value={newInstallment.amount_due}
            onChange={(e) => setNewInstallment({ ...newInstallment, amount_due: e.target.value })}
            className="rounded-lg border px-3 py-2"
          />
          <button className="rounded-xl bg-green-600 px-4 py-2 text-white hover:bg-green-700">Добавить</button>
        </form>

        <table className="w-full border-collapse text-left">
          <thead>
            <tr className="bg-slate-100 text-sm text-slate-600">
              <th className="p-3">#</th>
              <th className="p-3">Дата</th>
              <th className="p-3">Сумма</th>
              <th className="p-3">Статус</th>
              <th className="p-3"></th>
            </tr>
          </thead>
          <tbody className="text-sm">
            {installments.length === 0 && (
              <tr>
                <td className="p-3 text-slate-500" colSpan={5}>
                  Нет платежей
                </td>
              </tr>
            )}
            {installments.map((p, idx) => (
              <tr key={p.id} className="border-b hover:bg-slate-50">
                <td className="p-3 font-semibold">{p.number}</td>
                <td className="p-3">
                  <input
                    type="date"
                    value={p.due_date}
                    onChange={(e) => {
                      const next = [...installments];
                      next[idx] = { ...p, due_date: e.target.value };
                      setInstallments(next);
                    }}
                    className="w-full rounded-lg border px-2 py-1"
                  />
                </td>
                <td className="p-3">
                  <input
                    type="number"
                    value={p.amount_due}
                    onChange={(e) => {
                      const next = [...installments];
                      next[idx] = { ...p, amount_due: e.target.value };
                      setInstallments(next);
                    }}
                    className="w-full rounded-lg border px-2 py-1"
                  />
                </td>
                <td className="p-3">
                  <input
                    type="text"
                    value={p.status}
                    onChange={(e) => {
                      const next = [...installments];
                      next[idx] = { ...p, status: e.target.value };
                      setInstallments(next);
                    }}
                    className="w-full rounded-lg border px-2 py-1"
                  />
                </td>
                <td className="p-3 text-right">
                  <button
                    type="button"
                    onClick={() => setDeleteTarget({ type: "installment", id: p.id })}
                    className="text-red-600"
                  >
                    ✖
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        <button
          type="button"
          onClick={saveInstallments}
          className="mt-4 rounded-xl bg-blue-600 px-5 py-2 text-white hover:bg-blue-700"
        >
          Сохранить изменения
        </button>
      </section>

      <section className="space-y-4 rounded-2xl bg-white p-6 shadow-md">
        <h2 className="text-xl font-bold text-slate-700">Сводка платежей</h2>
        <div className="grid grid-cols-1 gap-6 text-sm md:grid-cols-2">
          <div className="rounded-xl border bg-slate-50 p-4">
            <p className="text-slate-500">Сумма всех платежей по рассрочке</p>
            <p className="text-xl font-bold text-slate-700">{total_installments_sum} ₽</p>
          </div>
          <div className="rounded-xl border bg-slate-50 p-4">
            <p className="text-slate-500">Сумма всех фактических оплат</p>
            <p className="text-xl font-bold text-slate-700">{total_actuals_sum} ₽</p>
          </div>
        </div>
      </section>

      <section className="space-y-6 rounded-2xl bg-white p-6 shadow-md">
        <h2 className="text-xl font-bold text-slate-700">Фактические оплаты</h2>
        <form onSubmit={addActual} className="flex items-center gap-4">
          <input
            type="date"
            required
            value={newActual.payment_date}
            onChange={(e) => setNewActual({ ...newActual, payment_date: e.target.value })}
            className="rounded-lg border px-3 py-2"
          />
          <input
            type="number"
            required
            placeholder="Сумма"
            value={newActual.amount}
            onChange={(e) => setNewActual({ ...newActual, amount: e.target.value })}
            className="rounded-lg border px-3 py-2"
          />
          <button className="rounded-xl bg-green-600 px-4 py-2 text-white hover:bg-green-700">Добавить</button>
        </form>

        <table className="w-full border-collapse text-left">
          <thead>
            <tr className="bg-slate-100 text-sm text-slate-600">
              <th className="p-3">Дата</th>
              <th className="p-3">Сумма</th>
              <th className="p-3"></th>
            </tr>
          </thead>
          <tbody className="text-sm">
            {actuals.length === 0 && (
              <tr>
                <td className="p-3 text-slate-500" colSpan={3}>
                  Нет оплат
                </td>
              </tr>
            )}
            {actuals.map((p, idx) => (
              <tr key={p.id} className="border-b hover:bg-slate-50">
                <td className="p-3">
                  <input
                    type="date"
                    value={p.payment_date || ""}
                    onChange={(e) => {
                      const next = [...actuals];
                      next[idx] = { ...p, payment_date: e.target.value };
                      setActuals(next);
                    }}
                    className="w-full rounded-lg border px-2 py-1"
                  />
                </td>
                <td className="p-3">
                  <input
                    type="number"
                    value={p.amount}
                    onChange={(e) => {
                      const next = [...actuals];
                      next[idx] = { ...p, amount: e.target.value };
                      setActuals(next);
                    }}
                    className="w-full rounded-lg border px-2 py-1"
                  />
                </td>
                <td className="p-3 text-right">
                  <button
                    type="button"
                    onClick={() => setDeleteTarget({ type: "actual", id: p.id })}
                    className="text-red-600"
                  >
                    ✖
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        <button
          type="button"
          onClick={saveActuals}
          className="mt-4 rounded-xl bg-blue-600 px-5 py-2 text-white hover:bg-blue-700"
        >
          Сохранить изменения
        </button>
      </section>

      <section className="space-y-6 rounded-2xl bg-white p-6 shadow-md">
        <h2 className="text-xl font-bold text-slate-700">Прочие платежи</h2>
        <form onSubmit={addOther} className="flex items-center gap-4">
          <select
            required
            value={newOther.payment_type}
            onChange={(e) => setNewOther({ ...newOther, payment_type: e.target.value })}
            className="rounded-lg border px-3 py-2"
          >
            <option value="">Тип платежа</option>
            {OTHER_PAYMENT_TYPES.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>
          <input
            type="number"
            required
            placeholder="Сумма"
            value={newOther.amount}
            onChange={(e) => setNewOther({ ...newOther, amount: e.target.value })}
            className="rounded-lg border px-3 py-2"
          />
          <input
            type="text"
            placeholder="Комментарий"
            value={newOther.comment}
            onChange={(e) => setNewOther({ ...newOther, comment: e.target.value })}
            className="w-64 rounded-lg border px-3 py-2"
          />
          <button className="rounded-xl bg-green-600 px-4 py-2 text-white hover:bg-green-700">Добавить</button>
        </form>

        <table className="w-full border-collapse text-left">
          <thead>
            <tr className="bg-slate-100 text-sm text-slate-600">
              <th className="p-3">Тип</th>
              <th className="p-3">Сумма</th>
              <th className="p-3">Комментарий</th>
              <th className="p-3"></th>
            </tr>
          </thead>
          <tbody className="text-sm">
            {others.length === 0 && (
              <tr>
                <td className="p-3 text-slate-500" colSpan={4}>
                  Нет прочих платежей
                </td>
              </tr>
            )}
            {others.map((op, idx) => (
              <tr key={op.id} className="border-b hover:bg-slate-50">
                <td className="p-3">
                  <select
                    value={op.payment_type}
                    onChange={(e) => {
                      const next = [...others];
                      next[idx] = { ...op, payment_type: e.target.value };
                      setOthers(next);
                    }}
                    className="w-full rounded-lg border px-2 py-1"
                  >
                    {OTHER_PAYMENT_TYPES.map((t) => (
                      <option key={t.value} value={t.value}>
                        {t.label}
                      </option>
                    ))}
                  </select>
                </td>
                <td className="p-3">
                  <input
                    type="number"
                    value={op.amount}
                    onChange={(e) => {
                      const next = [...others];
                      next[idx] = { ...op, amount: e.target.value };
                      setOthers(next);
                    }}
                    className="w-full rounded-lg border px-2 py-1"
                  />
                </td>
                <td className="p-3">
                  <input
                    type="text"
                    value={op.comment || ""}
                    onChange={(e) => {
                      const next = [...others];
                      next[idx] = { ...op, comment: e.target.value };
                      setOthers(next);
                    }}
                    className="w-full rounded-lg border px-2 py-1"
                  />
                </td>
                <td className="p-3 text-right">
                  <button
                    type="button"
                    onClick={() => setDeleteTarget({ type: "other", id: op.id })}
                    className="text-red-600"
                  >
                    ✖
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        <button
          type="button"
          onClick={saveOthers}
          className="mt-4 rounded-xl bg-blue-600 px-5 py-2 text-white hover:bg-blue-700"
        >
          Сохранить изменения
        </button>
      </section>

      {deleteTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
          <div className="w-full max-w-md space-y-4 rounded-2xl bg-white p-6 shadow-xl">
            <h3 className="text-xl font-bold text-slate-800">Удалить запись?</h3>
            <p className="text-slate-600">Вы уверены, что хотите удалить этот платёж? Это действие необратимо.</p>
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
