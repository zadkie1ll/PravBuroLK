import { FormEvent, useEffect, useState } from "react";
import { BotBlockItem, DictionariesResponse, DictionaryItem, marketingApi } from "../api/client";

const badgeClass = (active: boolean) =>
  `rounded-full px-2 py-0.5 text-xs font-medium ${active ? "bg-green-100 text-green-700" : "bg-gray-200 text-gray-600"}`;

function Toggle({ active, onClick }: { active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="rounded-md bg-[#1c1c1e] px-3 py-1 text-xs font-medium text-white transition hover:bg-[#333]"
    >
      {active ? "Скрыть" : "Показать"}
    </button>
  );
}

export function DictionariesPage() {
  const [data, setData] = useState<DictionariesResponse | null>(null);
  const [newSourceCode, setNewSourceCode] = useState("");
  const [newMediumCode, setNewMediumCode] = useState("");

  function load() {
    marketingApi.dictionaries(true).then(setData);
  }

  useEffect(load, []);

  async function addSource(e: FormEvent) {
    e.preventDefault();
    if (!newSourceCode.trim()) return;
    await marketingApi.addUtmSource(newSourceCode.trim().toLowerCase());
    setNewSourceCode("");
    load();
  }

  async function addMedium(e: FormEvent) {
    e.preventDefault();
    if (!newMediumCode.trim()) return;
    await marketingApi.addUtmMedium(newMediumCode.trim().toLowerCase());
    setNewMediumCode("");
    load();
  }

  if (!data) return null;

  return (
    <div className="mx-auto max-w-xl space-y-6">
      <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
        <h2 className="mb-3 text-sm font-semibold">utm_source</h2>
        <div className="divide-y divide-gray-100">
          {data.utm_sources.map((s: DictionaryItem) => (
            <div key={s.id} className="flex items-center justify-between py-2">
              <div className="flex items-center gap-2">
                <span className={s.is_active ? "" : "text-gray-400"}>{s.code}</span>
                <span className={badgeClass(s.is_active)}>{s.is_active ? "активен" : "скрыт"}</span>
              </div>
              <Toggle active={s.is_active} onClick={() => marketingApi.toggleUtmSource(s.id).then(load)} />
            </div>
          ))}
        </div>
        <form onSubmit={addSource} className="mt-3 flex gap-2">
          <input
            placeholder="новый utm_source, например vk-ivan"
            pattern="[a-z0-9\-]+"
            value={newSourceCode}
            onChange={(e) => setNewSourceCode(e.target.value)}
            className="flex-1 rounded-lg border border-gray-300 px-3 py-1.5 text-sm focus:border-gray-500 focus:outline-none focus:ring-1 focus:ring-gray-500"
          />
          <button type="submit" className="rounded-lg bg-[#1c1c1e] px-3 py-1.5 text-sm font-medium text-white hover:bg-[#333]">
            Добавить
          </button>
        </form>
      </div>

      <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
        <h2 className="mb-3 text-sm font-semibold">utm_medium</h2>
        <div className="divide-y divide-gray-100">
          {data.utm_mediums.map((m: DictionaryItem) => (
            <div key={m.id} className="flex items-center justify-between py-2">
              <div className="flex items-center gap-2">
                <span className={m.is_active ? "" : "text-gray-400"}>{m.code}</span>
                <span className={badgeClass(m.is_active)}>{m.is_active ? "активен" : "скрыт"}</span>
              </div>
              <Toggle active={m.is_active} onClick={() => marketingApi.toggleUtmMedium(m.id).then(load)} />
            </div>
          ))}
        </div>
        <form onSubmit={addMedium} className="mt-3 flex gap-2">
          <input
            placeholder="новый utm_medium"
            pattern="[a-z0-9\-]+"
            value={newMediumCode}
            onChange={(e) => setNewMediumCode(e.target.value)}
            className="flex-1 rounded-lg border border-gray-300 px-3 py-1.5 text-sm focus:border-gray-500 focus:outline-none focus:ring-1 focus:ring-gray-500"
          />
          <button type="submit" className="rounded-lg bg-[#1c1c1e] px-3 py-1.5 text-sm font-medium text-white hover:bg-[#333]">
            Добавить
          </button>
        </form>
      </div>

      <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
        <h2 className="mb-3 text-sm font-semibold">Блоки бота</h2>
        <div className="divide-y divide-gray-100">
          {data.bot_blocks.map((b: BotBlockItem) => (
            <div key={b.id} className="flex items-center justify-between py-2">
              <div className="flex items-center gap-2">
                <span className={b.is_active ? "" : "text-gray-400"}>
                  {b.key} — {b.title}
                </span>
                <span className={badgeClass(b.is_active)}>{b.is_active ? "активен" : "скрыт"}</span>
              </div>
              <Toggle active={b.is_active} onClick={() => marketingApi.toggleBotBlock(b.id).then(load)} />
            </div>
          ))}
        </div>
        <p className="mt-3 text-xs text-gray-400">
          Блоки создаются в админке бота — здесь можно только скрыть/показать уже существующие.
        </p>
      </div>

      <p className="text-center text-xs text-gray-400">
        Значения не удаляются насовсем — «Скрыть» просто убирает их из выпадающих списков при создании новых ссылок.
        Уже созданные ссылки со скрытым значением продолжают работать как обычно.
      </p>
    </div>
  );
}
