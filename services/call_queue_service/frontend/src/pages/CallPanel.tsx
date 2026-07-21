import { useEffect, useRef, useState } from 'react';
import { api, CallSnapshot, QueueItem } from "../api/client";

interface Props {
  item: QueueItem;
  autoDialEnabled: boolean;
  onQueueRefresh: () => void;
}

/**
 * Панель "Текущий звонок" — перенос инлайн-скрипта production_handler.html:385-600
 * (поллинг статуса звонка каждые 3с, модалка "Клиент взял трубку?", авто-переход к следующему).
 */
export function CallPanel({ item, autoDialEnabled, onQueueRefresh }: Props) {
  const callId = item.call_id;

  const [snapshot, setSnapshot] = useState<CallSnapshot | null>(null);
  const [paused, setPaused] = useState(!autoDialEnabled);
  const [decision, setDecision] = useState(item.manual_decision || "");
  const [showModal, setShowModal] = useState(false);
  const [expandedTimeline, setExpandedTimeline] = useState(false);
  const [error, setError] = useState("");

  const pausedRef = useRef(paused);
  const decisionRef = useRef(decision);
  const autoAdvanceTriggeredRef = useRef(false);
  const latestSnapshotRef = useRef<CallSnapshot | null>(null);

  // Телефон менеджера (SIP-клиент) не успевает закрыть предыдущую сессию звонка
  // сразу после его завершения, из-за чего мгновенный авто-дозвон на следующий
  // номер физически не доходит. Даём телефону время освободиться.
  const AUTO_NEXT_DELAY_MS = 6000;

  useEffect(() => {
    pausedRef.current = paused;
  }, [paused]);
  useEffect(() => {
    decisionRef.current = decision;
  }, [decision]);

  useEffect(() => {
    // новый звонок — сбрасываем локальное состояние панели
    setSnapshot(null);
    setPaused(!autoDialEnabled);
    setDecision(item.manual_decision || "");
    setShowModal(false);
    autoAdvanceTriggeredRef.current = false;
    latestSnapshotRef.current = null;
  }, [callId]); // eslint-disable-line react-hooks/exhaustive-deps

  async function triggerNext(forceResume = false, delayMs = 0) {
    if (pausedRef.current || autoAdvanceTriggeredRef.current) return;
    autoAdvanceTriggeredRef.current = true;
    try {
      if (delayMs > 0) {
        await new Promise((resolve) => setTimeout(resolve, delayMs));
        if (pausedRef.current) return;
      }
      const data = await api.triggerAutoNext(callId, forceResume);
      if (data.started) {
        onQueueRefresh();
        return;
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось перейти к следующему номеру");
    } finally {
      autoAdvanceTriggeredRef.current = false;
    }
  }

  function evaluate(snap: CallSnapshot | null) {
    if (!snap) return;
    const clientAnswered = snap.last_event_type === "ACCEPTED" && snap.last_event_direction === "out";
    if (clientAnswered && !decisionRef.current) {
      setPaused(true);
      pausedRef.current = true;
      setShowModal(true);
    }
    if (!snap.latest_history_status) return;
    if (decisionRef.current === "answered") {
      setPaused(true);
      pausedRef.current = true;
      return;
    }
    if (decisionRef.current === "failed" || decisionRef.current === "voicemail") {
      if (!pausedRef.current) triggerNext(false, AUTO_NEXT_DELAY_MS);
      return;
    }
    if (!clientAnswered) {
      if (!pausedRef.current) triggerNext(false, AUTO_NEXT_DELAY_MS);
    }
  }

  async function poll() {
    try {
      const data = await api.getMegafonStatus(callId);
      latestSnapshotRef.current = data.snapshot;
      setSnapshot(data.snapshot);
      evaluate(data.snapshot);
    } catch {
      /* временная сетевая ошибка — попробуем на следующем тике */
    }
  }

  useEffect(() => {
    if (!callId) return;
    poll();
    const interval = setInterval(poll, 3000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [callId]);

  async function submitDecision(value: string, openWhatsapp: boolean) {
    let bitrixWindow: Window | null = null;
    let whatsappWindow: Window | null = null;
    if (value === "answered") {
      bitrixWindow = window.open("about:blank", "_blank");
    }
    if (openWhatsapp) {
      setPaused(true);
      pausedRef.current = true;
      if (item.whatsapp_followup_url) {
        whatsappWindow = window.open("about:blank", "_blank");
      }
    }
    try {
      const data = await api.resolveMegafonCall(callId, value);
      setDecision(value);
      decisionRef.current = value;
      const nextPaused = value === "answered" || openWhatsapp;
      setPaused(nextPaused);
      pausedRef.current = nextPaused;
      setShowModal(false);
      if (value === "answered" && data.bitrix_url) {
        if (bitrixWindow && !bitrixWindow.closed) {
          bitrixWindow.location.href = data.bitrix_url;
        } else {
          window.open(data.bitrix_url, "_blank", "noopener");
        }
      } else if (bitrixWindow && !bitrixWindow.closed) {
        bitrixWindow.close();
      }
      if (openWhatsapp && item.whatsapp_followup_url) {
        if (whatsappWindow && !whatsappWindow.closed) {
          whatsappWindow.location.href = item.whatsapp_followup_url;
        } else {
          window.open(item.whatsapp_followup_url, "_blank", "noopener");
        }
      }
      evaluate(latestSnapshotRef.current);
    } catch (err) {
      if (bitrixWindow && !bitrixWindow.closed) bitrixWindow.close();
      if (whatsappWindow && !whatsappWindow.closed) whatsappWindow.close();
      setError(err instanceof Error ? err.message : "Не удалось сохранить решение");
    }
  }

  function handlePauseToggle() {
    const wasPaused = paused;
    const next = !paused;
    setPaused(next);
    pausedRef.current = next;
    autoAdvanceTriggeredRef.current = false;
    if (wasPaused && !next && latestSnapshotRef.current?.latest_history_status && decisionRef.current === "answered") {
      triggerNext(true);
      return;
    }
    evaluate(latestSnapshotRef.current);
  }

  return (
    <section className="mb-6 rounded-3xl bg-white p-6 shadow-lg ring-1 ring-slate-200">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-semibold">Текущий звонок</h2>
          <p className="mt-1 text-sm text-slate-500">
            Call ID: <span className="font-mono">{callId}</span>
          </p>
        </div>
        <div className="rounded-full bg-slate-100 px-4 py-2 text-sm font-medium text-slate-700">
          {snapshot ? snapshot.marker.label : "Ожидаем события"}
        </div>
      </div>

      {error && <div className="mt-3 rounded-2xl border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700">{error}</div>}

      <div className="mt-4 grid gap-4 md:grid-cols-4">
        <div className="rounded-2xl bg-slate-50 p-4">
          <div className="text-sm text-slate-500">Клиент</div>
          <div className="mt-1 font-medium">{item.client_name || "Без имени"}</div>
        </div>
        <div className="rounded-2xl bg-slate-50 p-4">
          <div className="text-sm text-slate-500">Телефон</div>
          <div className="mt-1 font-medium">{item.phone}</div>
        </div>
        <div className="rounded-2xl bg-slate-50 p-4">
          <div className="text-sm text-slate-500">История</div>
          <div className="mt-1 font-medium">{snapshot?.latest_history_status || "—"}</div>
        </div>
        <div className="rounded-2xl bg-slate-50 p-4">
          <div className="text-sm text-slate-500">Пауза</div>
          <div className="mt-1 font-medium">{paused ? "Включена" : "Выключена"}</div>
        </div>
      </div>

      <div className="mt-5 flex flex-wrap gap-3">
        <button
          onClick={handlePauseToggle}
          className="rounded-full bg-slate-900 px-5 py-3 text-sm font-medium text-white transition hover:bg-slate-700"
        >
          {paused ? "Возобновить" : "Пауза"}
        </button>
        {autoDialEnabled && (
          <div className="rounded-full bg-emerald-50 px-4 py-3 text-sm text-emerald-800 ring-1 ring-emerald-200">
            Автопрозвон активен: после первого старта очередь сама пойдёт дальше по недозвонам.
          </div>
        )}
      </div>

      <details
        className="mt-6 rounded-2xl border border-slate-200"
        open={expandedTimeline}
        onToggle={(e) => setExpandedTimeline((e.target as HTMLDetailsElement).open)}
      >
        <summary className="cursor-pointer select-none px-4 py-3 text-sm font-medium text-slate-500 transition hover:text-slate-900">
          Технические события звонка (МегаФон)
        </summary>
        <div className="space-y-3 px-4 pb-4">
          {snapshot && snapshot.timeline.length > 0 ? (
            snapshot.timeline.map((entry, idx) => (
              <div key={idx} className="rounded-2xl border border-slate-200 p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="font-medium text-slate-900">{entry.title_human || entry.title}</div>
                  <div className="text-xs text-slate-500">{entry.created_at}</div>
                </div>
                <div className="mt-2 text-xs text-slate-400">
                  direction: {entry.direction || "—"} | cmd: {entry.cmd || "—"} | type: {entry.type || "—"} | status:{" "}
                  {entry.status || "—"}
                </div>
              </div>
            ))
          ) : (
            <div className="rounded-2xl border border-dashed border-slate-300 px-4 py-8 text-center text-sm text-slate-500">
              Событий по звонку пока нет.
            </div>
          )}
        </div>
      </details>

      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/40 px-4">
          <div className="w-full max-w-lg rounded-3xl bg-white p-6 shadow-2xl">
            <div className="text-sm uppercase tracking-[0.2em] text-slate-500">Подтверждение дозвона</div>
            <h3 className="mt-2 text-2xl font-semibold text-slate-900">Клиент взял трубку?</h3>
            <p className="mt-3 text-sm text-slate-600">
              Подтвердите итог. Если клиент ответил, карточка сделки сразу откроется в новой вкладке.
            </p>
            <div className="mt-6 grid gap-3 sm:grid-cols-2">
              <button
                onClick={() => submitDecision("answered", false)}
                className="rounded-2xl bg-emerald-600 px-4 py-3 text-sm font-medium text-white transition hover:bg-emerald-500"
              >
                Клиент взял трубку
              </button>
              <button
                onClick={() => submitDecision("failed", false)}
                className="rounded-2xl bg-rose-600 px-4 py-3 text-sm font-medium text-white transition hover:bg-rose-500"
              >
                Недозвон
              </button>
              <button
                onClick={() => submitDecision("voicemail", false)}
                className="rounded-2xl bg-amber-500 px-4 py-3 text-sm font-medium text-white transition hover:bg-amber-400"
              >
                Автоответчик
              </button>
              <button
                onClick={() => submitDecision("failed", true)}
                className="rounded-2xl bg-green-600 px-4 py-3 text-sm font-medium text-white transition hover:bg-green-500"
              >
                Недозвон, написать в WhatsApp
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
