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

const inputClass =
  "w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-[#1c1c1e] focus:border-gray-500 focus:outline-none focus:ring-1 focus:ring-gray-500";
const cellInputClass =
  "w-full rounded-md border border-gray-300 px-2 py-1 text-sm text-[#1c1c1e] focus:border-gray-500 focus:outline-none focus:ring-1 focus:ring-gray-500";
const primaryBtn = "rounded-lg bg-[#1c1c1e] px-5 py-2 text-sm font-medium text-white transition hover:bg-[#333]";
const addBtn = "rounded-lg bg-[#1c1c1e] px-4 py-2 text-sm font-medium text-white transition hover:bg-[#333]";
const cardClass = "rounded-xl border border-gray-200 bg-white p-6 shadow-sm";
const sectionTitleClass = "text-base font-semibold text-[#1c1c1e]";
const thClass = "px-3 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-gray-500";

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
      <div className="mx-auto max-w-3xl bg-[#f7f7f8] py-10 text-center">
        <p className="mb-4 text-sm text-red-600">{error}</p>
        <Link to="/" className="text-sm font-medium text-[#1c1c1e] underline">
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
    <div className="min-h-screen bg-[#f7f7f8]">
      <div className="mx-auto max-w-6xl space-y-6 px-6 py-8">
        <div className="flex flex-wrap items-center gap-3">
          <Link
            to="/"
            className="inline-block rounded-lg bg-white border border-gray-300 px-4 py-2 text-sm font-medium text-[#1c1c1e] transition hover:bg-gray-50"
          >
            ← Назад к поиску клиентов
          </Link>
          <Link to={data.withdrawals_url} className={primaryBtn}>
            Списания клиента
          </Link>
          <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-2 text-sm font-medium text-amber-800">
            Общий хвост по снятиям: {data.total_tail_amount} ₽
          </div>
        </div>

        {client.is_blocked && (
          <div className="rounded-lg bg-red-600 p-3 text-center text-sm font-semibold text-white">
            Этот клиент заблокирован.
          </div>
        )}

        <section className={cardClass}>
          <h2 className={`mb-4 ${sectionTitleClass}`}>Данные клиента</h2>
          <div className="grid grid-cols-1 gap-4 text-sm md:grid-cols-3">
            <div>
              <span className="block text-xs font-semibold uppercase tracking-wide text-gray-500">Фамилия</span>
              <span className="block font-medium text-[#1c1c1e]">{client.surname}</span>
            </div>
            <div>
              <span className="block text-xs font-semibold uppercase tracking-wide text-gray-500">Имя</span>
              <span className="block font-medium text-[#1c1c1e]">{client.name}</span>
            </div>
            <div>
              <span className="block text-xs font-semibold uppercase tracking-wide text-gray-500">Сделка в Bitrix</span>
              {data.bitrix_deal_url ? (
                <a
                  href={data.bitrix_deal_url}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-1 inline-flex items-center gap-2 rounded-lg bg-[#1c1c1e] px-3 py-1.5 text-sm font-medium text-white transition hover:bg-[#333]"
                >
                  Открыть сделку
                </a>
              ) : (
                <span className="text-sm text-gray-400">нет bitrix_id</span>
              )}
            </div>
            <div>
              <span className="block text-xs font-semibold uppercase tracking-wide text-gray-500">Отчество</span>
              <span className="block font-medium text-[#1c1c1e]">{client.middlename}</span>
            </div>
          </div>
        </section>

        <section className={`space-y-4 ${cardClass}`}>
          <h2 className={sectionTitleClass}>Информация о контракте</h2>
          <form onSubmit={saveContract} className="space-y-4">
            <div className="grid grid-cols-1 gap-4 text-sm md:grid-cols-2">
              <div>
                <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-gray-500">Общая сумма</p>
                <input
                  type="number"
                  step="0.01"
                  required
                  value={contractForm.total_amount}
                  onChange={(e) => setContractForm({ ...contractForm, total_amount: e.target.value })}
                  className={inputClass}
                />
              </div>
              <div>
                <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-gray-500">Скидка</p>
                <input
                  type="number"
                  step="0.01"
                  required
                  value={contractForm.discount}
                  onChange={(e) => setContractForm({ ...contractForm, discount: e.target.value })}
                  className={inputClass}
                />
              </div>
              <div>
                <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-gray-500">Первый платеж</p>
                <input
                  type="number"
                  step="0.01"
                  required
                  value={contractForm.first_payment}
                  onChange={(e) => setContractForm({ ...contractForm, first_payment: e.target.value })}
                  className={inputClass}
                />
              </div>
              <div>
                <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-gray-500">Дата первого платежа</p>
                <input
                  type="date"
                  required
                  value={contractForm.first_payment_date}
                  onChange={(e) => setContractForm({ ...contractForm, first_payment_date: e.target.value })}
                  className={inputClass}
                />
              </div>
              <div>
                <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-gray-500">Количество платежей</p>
                <input
                  type="number"
                  min={1}
                  required
                  value={contractForm.number_of_payments}
                  onChange={(e) => setContractForm({ ...contractForm, number_of_payments: e.target.value })}
                  className={inputClass}
                />
              </div>
            </div>
            <button type="submit" className={primaryBtn}>
              Сохранить изменения
            </button>
          </form>
        </section>

        {amountsMismatch && (
          <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800">
            <b>Сумма платежей по рассрочке не совпадает с суммой по договору!</b>
            <br />
            По договору (с учётом скидки): {contract_final_amount} ₽<br />
            По рассрочке: {total_installments_sum} ₽
          </div>
        )}

        <section className={`space-y-4 ${cardClass}`}>
          <h2 className={sectionTitleClass}>Платежи по плану</h2>
          <form onSubmit={addInstallment} className="flex flex-wrap items-center gap-3">
            <input
              type="date"
              required
              value={newInstallment.due_date}
              onChange={(e) => setNewInstallment({ ...newInstallment, due_date: e.target.value })}
              className={`${inputClass} w-auto`}
            />
            <input
              type="number"
              required
              placeholder="Сумма"
              value={newInstallment.amount_due}
              onChange={(e) => setNewInstallment({ ...newInstallment, amount_due: e.target.value })}
              className={`${inputClass} w-auto`}
            />
            <button className={addBtn}>Добавить</button>
          </form>

          <div className="overflow-hidden rounded-lg border border-gray-200">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="bg-gray-50">
                  <th className={thClass}>#</th>
                  <th className={thClass}>Дата</th>
                  <th className={thClass}>Сумма</th>
                  <th className={thClass}>Статус</th>
                  <th className={thClass}></th>
                </tr>
              </thead>
              <tbody>
                {installments.length === 0 && (
                  <tr>
                    <td className="px-3 py-2.5 text-gray-400" colSpan={5}>
                      Нет платежей
                    </td>
                  </tr>
                )}
                {installments.map((p, idx) => (
                  <tr key={p.id} className="border-t border-gray-100 hover:bg-gray-50">
                    <td className="px-3 py-2 font-medium text-[#1c1c1e]">{p.number}</td>
                    <td className="px-3 py-2">
                      <input
                        type="date"
                        value={p.due_date}
                        onChange={(e) => {
                          const next = [...installments];
                          next[idx] = { ...p, due_date: e.target.value };
                          setInstallments(next);
                        }}
                        className={cellInputClass}
                      />
                    </td>
                    <td className="px-3 py-2">
                      <input
                        type="number"
                        value={p.amount_due}
                        onChange={(e) => {
                          const next = [...installments];
                          next[idx] = { ...p, amount_due: e.target.value };
                          setInstallments(next);
                        }}
                        className={cellInputClass}
                      />
                    </td>
                    <td className="px-3 py-2">
                      <input
                        type="text"
                        value={p.status}
                        onChange={(e) => {
                          const next = [...installments];
                          next[idx] = { ...p, status: e.target.value };
                          setInstallments(next);
                        }}
                        className={cellInputClass}
                      />
                    </td>
                    <td className="px-3 py-2 text-right">
                      <button
                        type="button"
                        onClick={() => setDeleteTarget({ type: "installment", id: p.id })}
                        className="text-sm font-medium text-red-600 hover:text-red-700"
                      >
                        Удалить
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <button type="button" onClick={saveInstallments} className={primaryBtn}>
            Сохранить изменения
          </button>
        </section>

        <section className={`space-y-4 ${cardClass}`}>
          <h2 className={sectionTitleClass}>Сводка платежей</h2>
          <div className="grid grid-cols-1 gap-4 text-sm md:grid-cols-2">
            <div className="rounded-xl border border-gray-200 bg-[#f7f7f8] p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">Сумма всех платежей по рассрочке</p>
              <p className="text-lg font-semibold text-[#1c1c1e]">{total_installments_sum} ₽</p>
            </div>
            <div className="rounded-xl border border-gray-200 bg-[#f7f7f8] p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">Сумма всех фактических оплат</p>
              <p className="text-lg font-semibold text-[#1c1c1e]">{total_actuals_sum} ₽</p>
            </div>
          </div>
        </section>

        <section className={`space-y-4 ${cardClass}`}>
          <h2 className={sectionTitleClass}>Фактические оплаты</h2>
          <form onSubmit={addActual} className="flex flex-wrap items-center gap-3">
            <input
              type="date"
              required
              value={newActual.payment_date}
              onChange={(e) => setNewActual({ ...newActual, payment_date: e.target.value })}
              className={`${inputClass} w-auto`}
            />
            <input
              type="number"
              required
              placeholder="Сумма"
              value={newActual.amount}
              onChange={(e) => setNewActual({ ...newActual, amount: e.target.value })}
              className={`${inputClass} w-auto`}
            />
            <button className={addBtn}>Добавить</button>
          </form>

          <div className="overflow-hidden rounded-lg border border-gray-200">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="bg-gray-50">
                  <th className={thClass}>Дата</th>
                  <th className={thClass}>Сумма</th>
                  <th className={thClass}></th>
                </tr>
              </thead>
              <tbody>
                {actuals.length === 0 && (
                  <tr>
                    <td className="px-3 py-2.5 text-gray-400" colSpan={3}>
                      Нет оплат
                    </td>
                  </tr>
                )}
                {actuals.map((p, idx) => (
                  <tr key={p.id} className="border-t border-gray-100 hover:bg-gray-50">
                    <td className="px-3 py-2">
                      <input
                        type="date"
                        value={p.payment_date || ""}
                        onChange={(e) => {
                          const next = [...actuals];
                          next[idx] = { ...p, payment_date: e.target.value };
                          setActuals(next);
                        }}
                        className={cellInputClass}
                      />
                    </td>
                    <td className="px-3 py-2">
                      <input
                        type="number"
                        value={p.amount}
                        onChange={(e) => {
                          const next = [...actuals];
                          next[idx] = { ...p, amount: e.target.value };
                          setActuals(next);
                        }}
                        className={cellInputClass}
                      />
                    </td>
                    <td className="px-3 py-2 text-right">
                      <button
                        type="button"
                        onClick={() => setDeleteTarget({ type: "actual", id: p.id })}
                        className="text-sm font-medium text-red-600 hover:text-red-700"
                      >
                        Удалить
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <button type="button" onClick={saveActuals} className={primaryBtn}>
            Сохранить изменения
          </button>
        </section>

        <section className={`space-y-4 ${cardClass}`}>
          <h2 className={sectionTitleClass}>Прочие платежи</h2>
          <form onSubmit={addOther} className="flex flex-wrap items-center gap-3">
            <select
              required
              value={newOther.payment_type}
              onChange={(e) => setNewOther({ ...newOther, payment_type: e.target.value })}
              className={`${inputClass} w-auto`}
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
              className={`${inputClass} w-auto`}
            />
            <input
              type="text"
              placeholder="Комментарий"
              value={newOther.comment}
              onChange={(e) => setNewOther({ ...newOther, comment: e.target.value })}
              className={`${inputClass} w-64`}
            />
            <button className={addBtn}>Добавить</button>
          </form>

          <div className="overflow-hidden rounded-lg border border-gray-200">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="bg-gray-50">
                  <th className={thClass}>Тип</th>
                  <th className={thClass}>Сумма</th>
                  <th className={thClass}>Комментарий</th>
                  <th className={thClass}></th>
                </tr>
              </thead>
              <tbody>
                {others.length === 0 && (
                  <tr>
                    <td className="px-3 py-2.5 text-gray-400" colSpan={4}>
                      Нет прочих платежей
                    </td>
                  </tr>
                )}
                {others.map((op, idx) => (
                  <tr key={op.id} className="border-t border-gray-100 hover:bg-gray-50">
                    <td className="px-3 py-2">
                      <select
                        value={op.payment_type}
                        onChange={(e) => {
                          const next = [...others];
                          next[idx] = { ...op, payment_type: e.target.value };
                          setOthers(next);
                        }}
                        className={cellInputClass}
                      >
                        {OTHER_PAYMENT_TYPES.map((t) => (
                          <option key={t.value} value={t.value}>
                            {t.label}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td className="px-3 py-2">
                      <input
                        type="number"
                        value={op.amount}
                        onChange={(e) => {
                          const next = [...others];
                          next[idx] = { ...op, amount: e.target.value };
                          setOthers(next);
                        }}
                        className={cellInputClass}
                      />
                    </td>
                    <td className="px-3 py-2">
                      <input
                        type="text"
                        value={op.comment || ""}
                        onChange={(e) => {
                          const next = [...others];
                          next[idx] = { ...op, comment: e.target.value };
                          setOthers(next);
                        }}
                        className={cellInputClass}
                      />
                    </td>
                    <td className="px-3 py-2 text-right">
                      <button
                        type="button"
                        onClick={() => setDeleteTarget({ type: "other", id: op.id })}
                        className="text-sm font-medium text-red-600 hover:text-red-700"
                      >
                        Удалить
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <button type="button" onClick={saveOthers} className={primaryBtn}>
            Сохранить изменения
          </button>
        </section>

        {deleteTarget && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
            <div className="w-full max-w-md space-y-4 rounded-xl border border-gray-200 bg-white p-6 shadow-xl">
              <h3 className="text-base font-semibold text-[#1c1c1e]">Удалить запись?</h3>
              <p className="text-sm text-gray-500">Вы уверены, что хотите удалить этот платёж? Это действие необратимо.</p>
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
    </div>
  );
}
