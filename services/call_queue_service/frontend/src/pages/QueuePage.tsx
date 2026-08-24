import { FormEvent, useEffect, useState } from "react";
import { api, QueueItem, QueueState } from "../api/client";
import { CallPanel } from "./CallPanel";

type BuildMode = "date" | "custom";

const ITEM_STATUS_BADGE: Record<string, string> = {
  answered: "bg-emerald-100 text-emerald-800",
  calling: "bg-amber-100 text-amber-800",
  voicemail: "bg-orange-100 text-orange-800",
  failed: "bg-rose-100 text-rose-800",
};

function itemBadge(item: QueueItem): { label: string; className: string } {
  if (item.manual_decision === "answered") return { label: "Клиент ответил", className: ITEM_STATUS_BADGE.answered };
  if (item.status === "calling") return { label: "В звонке", className: ITEM_STATUS_BADGE.calling };
  if (item.manual_decision === "voicemail") return { label: "Автоответчик", className: ITEM_STATUS_BADGE.voicemail };
  if (item.manual_decision === "failed" || item.status === "failed")
    return { label: "Недозвон", className: ITEM_STATUS_BADGE.failed };
  return { label: "Ожидает", className: "bg-slate-100 text-slate-700" };
}

function ItemCard({
  item,
  index,
  highlighted,
  onRemove,
}: {
  item: QueueItem;
  index: number;
  highlighted: boolean;
  onRemove: () => void;
}) {
  const badge = itemBadge(item);
  return (
    <div className={`rounded-3xl border p-5 ${highlighted ? "border-emerald-300 bg-emerald-50/60" : "border-slate-200 bg-white"}`}>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="text-xs uppercase tracking-[0.15em] text-slate-500">
            #{index + 1}
            {item.source === "custom" && (
              <span className="ml-2 rounded-full bg-sky-100 px-2 py-0.5 text-[10px] font-semibold text-sky-700">
                добавлено вручную
              </span>
            )}
          </div>
          <div className="mt-1 text-lg font-semibold text-slate-900">{item.client_name || "Без названия"}</div>
        </div>
        <span className={`rounded-full px-3 py-1 text-xs font-medium ${badge.className}`}>{badge.label}</span>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-4">
        <div className="rounded-2xl bg-slate-50 p-4 text-sm text-slate-700">
          <div className="text-xs uppercase tracking-[0.15em] text-slate-500">Контакты</div>
          <div className="mt-2">Bitrix: {item.raw_phone || item.phone}</div>
          <div className="mt-1 font-medium text-emerald-700">МегаФон: {item.phone}</div>
        </div>
        <div className="rounded-2xl bg-slate-50 p-4 text-sm text-slate-700">
          <div className="text-xs uppercase tracking-[0.15em] text-slate-500">Bitrix</div>
          <div className="mt-2">
            {item.entity_type === "lead" ? "Lead" : "Deal"} ID: {item.entity_id ?? item.deal_id ?? item.lead_id ?? "—"}
          </div>
          <div className="mt-1">
            {item.entity_type === "lead" ? "Статус" : "Стадия"}: {item.stage_id || "—"}
          </div>
        </div>
        <div className="rounded-2xl bg-slate-50 p-4 text-sm text-slate-700">
          <div className="text-xs uppercase tracking-[0.15em] text-slate-500">Регион по номеру</div>
          <div className="mt-2">{item.phone_insights?.region_label || "—"}</div>
        </div>
        <div className="rounded-2xl bg-slate-50 p-4 text-sm text-slate-700">
          <div className="text-xs uppercase tracking-[0.15em] text-slate-500">Локальное время</div>
          <div className="mt-2">
            {item.phone_insights?.local_time
              ? `${item.phone_insights.local_time} ${item.phone_insights.timezone_label || ""}`
              : "—"}
          </div>
        </div>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-[1fr_auto]">
        <div className="rounded-2xl bg-slate-50 p-4 text-sm text-slate-700">
          <div className="mb-2 text-xs uppercase tracking-[0.15em] text-slate-500">COMMENTS</div>
          {item.comments ? (
            <pre className="whitespace-pre-wrap font-sans">{item.comments}</pre>
          ) : (
            <div className="text-slate-400">Поле COMMENTS пока пустое.</div>
          )}
        </div>
        <div className="flex flex-wrap items-start gap-3">
          {item.bitrix_url && (
            <a
              href={item.bitrix_url}
              target="_blank"
              rel="noreferrer"
              className="rounded-full bg-white px-4 py-2 text-sm font-medium text-slate-900 shadow-sm ring-1 ring-slate-300 transition hover:bg-slate-100"
            >
              Открыть в Bitrix
            </a>
          )}
          {item.whatsapp_followup_url && (
            <a
              href={item.whatsapp_followup_url}
              className="rounded-full bg-emerald-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-emerald-500"
            >
              Написать в WhatsApp
            </a>
          )}
          {item.telegram_desktop_url && (
            <a
              href={item.telegram_desktop_url}
              className="rounded-full bg-sky-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-sky-500"
            >
              Telegram Desktop
            </a>
          )}
          <button
            type="button"
            onClick={async () => {
              window.open(item.max_followup_url || "https://max.ru/:share", "_blank", "noopener");
              try {
                await navigator.clipboard.writeText(item.phone);
              } catch {
                /* ignore clipboard issues */
              }
            }}
            className="rounded-full bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-700"
          >
            Написать в MAX
          </button>
          <button
            onClick={onRemove}
            className="rounded-full bg-white px-4 py-2 text-sm font-medium text-rose-700 shadow-sm ring-1 ring-rose-200 transition hover:bg-rose-50"
          >
            Удалить из очереди
          </button>
        </div>
      </div>
    </div>
  );
}

/** Соответствует call_queue/templates/call_queue/_current_item_card.html */
function CurrentItemCard({ item }: { item: QueueItem }) {
  return (
    <>
      <div className="text-sm text-slate-500">Текущий элемент</div>
      <div className="mt-2 text-lg font-semibold">{item.client_name || "Без имени"}</div>
      <div className="mt-3 grid gap-3 md:grid-cols-2">
        <div className="rounded-2xl bg-slate-50 p-4 text-sm text-slate-700">
          <div className="text-xs uppercase tracking-[0.15em] text-slate-500">Контакты</div>
          <div className="mt-2">Телефон из Bitrix: {item.raw_phone || item.phone}</div>
          <div className="mt-1 font-medium text-emerald-700">Телефон для МегаФона: {item.phone}</div>
        </div>
        <div className="rounded-2xl bg-slate-50 p-4 text-sm text-slate-700">
          <div className="text-xs uppercase tracking-[0.15em] text-slate-500">Bitrix</div>
          <div className="mt-2">
            {item.entity_type === "lead" ? "Lead" : "Deal"} ID: {item.entity_id ?? item.deal_id ?? item.lead_id ?? "—"}
          </div>
          <div className="mt-1">
            {item.entity_type === "lead" ? "Статус" : "Стадия"}: {item.stage_id || "—"}
          </div>
        </div>
        <div className="rounded-2xl bg-slate-50 p-4 text-sm text-slate-700">
          <div className="text-xs uppercase tracking-[0.15em] text-slate-500">Регион по номеру</div>
          <div className="mt-2">{item.phone_insights?.region_label || "—"}</div>
        </div>
        <div className="rounded-2xl bg-slate-50 p-4 text-sm text-slate-700">
          <div className="text-xs uppercase tracking-[0.15em] text-slate-500">Локальное время</div>
          <div className="mt-2">
            {item.phone_insights?.local_time
              ? `${item.phone_insights.local_time} ${item.phone_insights.timezone_label || ""}`
              : "—"}
          </div>
        </div>
      </div>
      {item.comments && (
        <div className="mt-4 rounded-2xl bg-slate-50 p-4 text-sm text-slate-700">
          <div className="mb-2 font-medium text-slate-900">COMMENTS</div>
          <pre className="whitespace-pre-wrap font-sans">{item.comments}</pre>
        </div>
      )}
      <div className="mt-4 flex flex-wrap gap-3">
        {item.bitrix_url && (
          <a
            href={item.bitrix_url}
            target="_blank"
            rel="noreferrer"
            className="rounded-full bg-white px-5 py-3 text-sm font-medium text-slate-900 shadow-sm ring-1 ring-slate-300 transition hover:bg-slate-100"
          >
            Открыть в Bitrix
          </a>
        )}
        {item.whatsapp_followup_url && (
          <a
            href={item.whatsapp_followup_url}
            className="rounded-full bg-emerald-600 px-5 py-3 text-sm font-medium text-white transition hover:bg-emerald-500"
          >
            Написать в WhatsApp
          </a>
        )}
        {item.telegram_desktop_url && (
          <a
            href={item.telegram_desktop_url}
            className="rounded-full bg-sky-600 px-5 py-3 text-sm font-medium text-white transition hover:bg-sky-500"
          >
            Telegram Desktop
          </a>
        )}
        <button
          type="button"
          onClick={async () => {
            window.open(item.max_followup_url || "https://max.ru/:share", "_blank", "noopener");
            try {
              await navigator.clipboard.writeText(item.phone);
            } catch {
              /* ignore clipboard issues */
            }
          }}
          className="rounded-full bg-slate-900 px-5 py-3 text-sm font-medium text-white transition hover:bg-slate-700"
        >
          Написать в MAX
        </button>
      </div>
      <p className="mt-3 text-xs text-slate-500">
        MAX откроет экран отправки с заготовленным текстом. Номер клиента скопируется в буфер для быстрого поиска чата.
      </p>
    </>
  );
}

export function QueuePage() {
  const [state, setState] = useState<QueueState | null>(null);
  const [error, setError] = useState("");
  const [mode, setMode] = useState<BuildMode>("date");

  const [entityType, setEntityType] = useState("deal");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [stageId, setStageId] = useState("");
  const [autoDial, setAutoDial] = useState(true);

  const [customEntityType, setCustomEntityType] = useState("deal");
  const [customQuery, setCustomQuery] = useState("");
  const [customCategoryId, setCustomCategoryId] = useState("");
  const [startingCall, setStartingCall] = useState(false);

  async function load() {
    setError("");
    try {
      setState(await api.getQueueState());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось загрузить очередь");
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function handleBuildQueue(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      setState(
        await api.buildQueue({
          entity_type: entityType,
          date_from: dateFrom,
          date_to: dateTo,
          stage_id: stageId,
          auto_dial: autoDial,
        })
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось загрузить очередь");
    }
  }

  async function handleAddCustom(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      setState(
        await api.addCustomItem({
          entity_type: customEntityType,
          query: customQuery,
          category_id: customCategoryId,
        })
      );
      setCustomQuery("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось добавить в очередь");
    }
  }

  async function handleReset() {
    setError("");
    try {
      setState(await api.resetQueue());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось очистить очередь");
    }
  }

  async function handleRemove(index: number) {
    setError("");
    try {
      setState(await api.removeItem(index));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось удалить элемент");
    }
  }

  async function handleStartCall() {
    setError("");
    setStartingCall(true);
    try {
      setState(await api.startCall());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось начать обзвон");
    } finally {
      setStartingCall(false);
    }
  }

  if (!state) {
    return (
      <div className="min-h-screen bg-slate-100 px-4 py-8">
        {error && <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-100 text-slate-900">
      <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6 lg:px-8">
        <div className="mb-8 rounded-3xl bg-gradient-to-r from-slate-900 via-slate-800 to-emerald-700 p-8 text-white shadow-2xl">
          <p className="mb-2 text-sm uppercase tracking-[0.3em] text-emerald-200">Call Queue</p>
          <h1 className="text-3xl font-semibold sm:text-4xl">Продовый обработчик очереди</h1>
          <p className="mt-3 max-w-3xl text-sm text-slate-200 sm:text-base">
            Менеджер выбирает даты, тип сущности и стадию из Bitrix24, а дальше идёт по очереди и фиксирует дозвон.
          </p>
        </div>

        {error && (
          <div className="mb-6 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>
        )}

        {state.current_item && state.current_item.call_id && (
          <CallPanel item={state.current_item} autoDialEnabled={state.auto_dial_enabled} onQueueRefresh={load} />
        )}

        <div className="grid gap-6 lg:grid-cols-[0.9fr_1.1fr]">
          <section className="rounded-3xl bg-white p-6 shadow-lg ring-1 ring-slate-200">
            <h2 className="text-xl font-semibold">Формирование очереди</h2>

            <div className="mt-4 flex gap-2">
              <button
                type="button"
                onClick={() => setMode("date")}
                className={`rounded-full px-4 py-2 text-sm font-medium transition ${
                  mode === "date" ? "bg-slate-900 text-white" : "bg-slate-100 text-slate-700"
                }`}
              >
                По датам
              </button>
              <button
                type="button"
                onClick={() => setMode("custom")}
                className={`rounded-full px-4 py-2 text-sm font-medium transition ${
                  mode === "custom" ? "bg-slate-900 text-white" : "bg-slate-100 text-slate-700"
                }`}
              >
                Кастомная очередь
              </button>
            </div>

            {mode === "date" ? (
              <form onSubmit={handleBuildQueue} className="mt-6 space-y-5">
                <div>
                  <label className="mb-2 block text-sm font-medium text-slate-700">Что обзваниваем</label>
                  <select
                    value={entityType}
                    onChange={(e) => setEntityType(e.target.value)}
                    className="w-full rounded-2xl border border-slate-300 px-4 py-3 outline-none focus:border-amber-500"
                  >
                    <option value="deal">Сделки</option>
                    <option value="lead">Лиды</option>
                  </select>
                </div>
                <div>
                  <label className="mb-2 block text-sm font-medium text-slate-700">Дата от</label>
                  <input
                    type="date"
                    value={dateFrom}
                    onChange={(e) => setDateFrom(e.target.value)}
                    required
                    className="w-full rounded-2xl border border-slate-300 px-4 py-3 outline-none focus:border-amber-500"
                  />
                </div>
                <div>
                  <label className="mb-2 block text-sm font-medium text-slate-700">Дата до</label>
                  <input
                    type="date"
                    value={dateTo}
                    onChange={(e) => setDateTo(e.target.value)}
                    required
                    className="w-full rounded-2xl border border-slate-300 px-4 py-3 outline-none focus:border-amber-500"
                  />
                </div>
                <div>
                  <label className="mb-2 block text-sm font-medium text-slate-700">
                    {entityType === "lead" ? "Статус лида" : "Стадия сделки"}
                  </label>
                  <select
                    value={stageId}
                    onChange={(e) => setStageId(e.target.value)}
                    className="w-full rounded-2xl border border-slate-300 px-4 py-3 outline-none focus:border-amber-500"
                  >
                    <option value="">Все стадии</option>
                    {state.stage_choices.map((choice) => (
                      <option key={choice.value} value={choice.value}>
                        {choice.label}
                      </option>
                    ))}
                  </select>
                </div>
                <label className="flex items-center gap-3 rounded-2xl border border-slate-200 px-4 py-3">
                  <input type="checkbox" checked={autoDial} onChange={(e) => setAutoDial(e.target.checked)} />
                  <span>Автоматически переходить к следующему номеру после недозвона</span>
                </label>
                <div className="flex flex-wrap gap-3">
                  <button
                    type="submit"
                    className="rounded-full bg-slate-900 px-5 py-3 text-sm font-medium text-white shadow-lg transition hover:bg-slate-700"
                  >
                    Загрузить очередь
                  </button>
                </div>
              </form>
            ) : (
              <div className="mt-6">
                <p className="mb-4 text-sm text-slate-500">
                  Введите номер телефона или имя клиента — карточка найдётся в Bitrix24 и добавится в конец текущей
                  очереди обзвона.
                </p>
                <form onSubmit={handleAddCustom} className="space-y-5">
                  <div>
                    <label className="mb-2 block text-sm font-medium text-slate-700">Что добавляем</label>
                    <select
                      value={customEntityType}
                      onChange={(e) => setCustomEntityType(e.target.value)}
                      className="w-full rounded-2xl border border-slate-300 px-4 py-3 outline-none focus:border-amber-500"
                    >
                      <option value="deal">Сделки</option>
                      <option value="lead">Лиды</option>
                    </select>
                  </div>
                  <div>
                    <label className="mb-2 block text-sm font-medium text-slate-700">Телефон или имя клиента</label>
                    <input
                      value={customQuery}
                      onChange={(e) => setCustomQuery(e.target.value)}
                      placeholder="Например: +7 900 123-45-67 или Иванов"
                      required
                      className="w-full rounded-2xl border border-slate-300 px-4 py-3 outline-none focus:border-amber-500"
                    />
                  </div>
                  {customEntityType === "deal" && (
                    <div>
                      <label className="mb-2 block text-sm font-medium text-slate-700">Канбан</label>
                      <select
                        value={customCategoryId}
                        onChange={(e) => setCustomCategoryId(e.target.value)}
                        className="w-full rounded-2xl border border-slate-300 px-4 py-3 outline-none focus:border-amber-500"
                      >
                        <option value="">Все канбаны</option>
                        {state.category_choices.map((choice) => (
                          <option key={choice.value} value={choice.value}>
                            {choice.label}
                          </option>
                        ))}
                      </select>
                    </div>
                  )}
                  <div className="flex flex-wrap gap-3">
                    <button
                      type="submit"
                      className="rounded-full bg-emerald-600 px-5 py-3 text-sm font-medium text-white shadow-lg transition hover:bg-emerald-500"
                    >
                      Добавить в очередь
                    </button>
                  </div>
                </form>
              </div>
            )}

            <button
              onClick={handleReset}
              className="mt-3 rounded-full bg-white px-5 py-3 text-sm font-medium text-slate-900 shadow-sm ring-1 ring-slate-300 transition hover:bg-slate-100"
            >
              Очистить очередь
            </button>
          </section>

          <aside className="flex flex-col rounded-3xl bg-white p-6 shadow-lg ring-1 ring-slate-200">
            <h2 className="text-xl font-semibold">Статус очереди</h2>

            {state.current_item && state.current_item.call_id ? (
              <div className="mt-5 rounded-2xl border border-dashed border-slate-300 px-4 py-6 text-center text-sm text-slate-500">
                Карточка клиента — выше, в блоке «Текущий звонок».
              </div>
            ) : state.current_item ? (
              <div className="mt-5 rounded-2xl border border-slate-200 p-4">
                <CurrentItemCard item={state.current_item} />
              </div>
            ) : (
              <div className="mt-5 rounded-2xl border border-dashed border-slate-300 px-4 py-8 text-center text-sm text-slate-500">
                Очередь пока не сформирована.
              </div>
            )}

            <div className="mt-5 grid gap-4 sm:grid-cols-3">
              <div className="rounded-2xl bg-slate-50 p-4">
                <div className="text-sm text-slate-500">Всего элементов</div>
                <div className="mt-1 text-2xl font-semibold">{state.queue_size}</div>
              </div>
              <div className="rounded-2xl bg-slate-50 p-4">
                <div className="text-sm text-slate-500">Текущая позиция</div>
                <div className="mt-1 text-2xl font-semibold">{state.queue_size ? state.current_index + 1 : 0}</div>
              </div>
              <div className="rounded-2xl bg-slate-50 p-4">
                <div className="text-sm text-slate-500">Менеджер</div>
                <div className="mt-1 text-lg font-semibold">{state.manager_name || "—"}</div>
              </div>
            </div>

            {state.queue_size > 0 && (
              <div className="mt-5 rounded-2xl border border-emerald-200 bg-emerald-50 p-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <div className="text-sm uppercase tracking-[0.15em] text-emerald-700">Старт обзвона</div>
                    <p className="mt-1 text-sm text-emerald-900">
                      Очередь сформирована. Можно сразу запустить {state.auto_dial_enabled ? "автопрозвон" : "обзвон"} с
                      текущего элемента.
                    </p>
                  </div>
                  <button
                    onClick={handleStartCall}
                    disabled={startingCall}
                    className="flex items-center gap-2 rounded-full bg-emerald-600 px-5 py-3 text-sm font-medium text-white shadow-lg transition hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-70"
                  >
                    {startingCall && (
                      <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
                      </svg>
                    )}
                    {startingCall ? "Подключаемся к АТС МегаФона..." : "Начать обзвон"}
                  </button>
                </div>
              </div>
            )}
          </aside>
        </div>

        {state.queue_size > 0 && (
          <section className="mt-6 rounded-3xl bg-white p-6 shadow-lg ring-1 ring-slate-200">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h3 className="text-xl font-semibold">{state.entity_type === "lead" ? "Лиды" : "Сделки"} в очереди</h3>
              <div className="text-sm text-slate-500">Полный список очереди с комментариями и подсказками по номеру</div>
            </div>
            <div className="mt-5 space-y-4">
              {state.queue.map((item, index) => (
                <ItemCard
                  key={`${item.entity_type}-${item.entity_id}-${index}`}
                  item={item}
                  index={index}
                  highlighted={index === state.current_index}
                  onRemove={() => handleRemove(index)}
                />
              ))}
            </div>
          </section>
        )}
      </div>
    </div>
  );
}
