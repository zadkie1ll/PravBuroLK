import { useEffect, useState } from "react";
import { DictionaryItem, MarketingStatsFilters, MarketingStatsResponse, marketingApi } from "../api/client";

const GROUP_OPTIONS: { value: string; label: string }[] = [
  { value: "full_link", label: "Полная ссылка (с крео)" },
  { value: "utm_source", label: "utm_source" },
  { value: "utm_medium", label: "utm_medium" },
  { value: "utm_campaign", label: "utm_campaign" },
  { value: "utm_content", label: "utm_content" },
  { value: "utm_term", label: "utm_term" },
  { value: "link_type", label: "Тип назначения" },
  { value: "destination", label: "Целевая ссылка" },
  { value: "bot_block", label: "Блок бота" },
];

const LINK_TYPES = [
  { value: "", label: "Все" },
  { value: "site", label: "Сайт" },
  { value: "bot", label: "Telegram-бот" },
  { value: "other", label: "Прочие площадки" },
];

const inputClass =
  "w-full rounded-lg border border-gray-300 px-3 py-1.5 text-sm text-[#1c1c1e] focus:border-gray-500 focus:outline-none focus:ring-1 focus:ring-gray-500";
const labelClass = "mb-1 block text-xs font-semibold text-gray-500";

export function MarketingStatsPage() {
  const [utmSources, setUtmSources] = useState<DictionaryItem[]>([]);
  const [utmMediums, setUtmMediums] = useState<DictionaryItem[]>([]);
  const [filters, setFilters] = useState<MarketingStatsFilters>({ group_by: "full_link", page: 1 });
  const [data, setData] = useState<MarketingStatsResponse | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    marketingApi.dictionaries().then((d) => {
      setUtmSources(d.utm_sources);
      setUtmMediums(d.utm_mediums);
    });
  }, []);

  useEffect(() => {
    setLoading(true);
    marketingApi
      .stats(filters)
      .then(setData)
      .finally(() => setLoading(false));
  }, [filters]);

  function set<K extends keyof MarketingStatsFilters>(key: K, value: MarketingStatsFilters[K]) {
    setFilters((prev) => {
      const next = { ...prev, [key]: value };
      if (key !== "page") next.page = 1;
      return next;
    });
  }

  const groupLabel = GROUP_OPTIONS.find((g) => g.value === filters.group_by)?.label ?? filters.group_by;

  return (
    <div className="space-y-6">
      <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
          <div>
            <label className={labelClass}>Клик — с</label>
            <input type="date" className={inputClass} value={filters.click_from ?? ""} onChange={(e) => set("click_from", e.target.value)} />
          </div>
          <div>
            <label className={labelClass}>Клик — по</label>
            <input type="date" className={inputClass} value={filters.click_to ?? ""} onChange={(e) => set("click_to", e.target.value)} />
          </div>
          <div>
            <label className={labelClass}>Публикация — с</label>
            <input type="date" className={inputClass} value={filters.created_from ?? ""} onChange={(e) => set("created_from", e.target.value)} />
          </div>
          <div>
            <label className={labelClass}>Публикация — по</label>
            <input type="date" className={inputClass} value={filters.created_to ?? ""} onChange={(e) => set("created_to", e.target.value)} />
          </div>
          <div>
            <label className={labelClass}>Группировать по</label>
            <select className={inputClass} value={filters.group_by} onChange={(e) => set("group_by", e.target.value)}>
              {GROUP_OPTIONS.map((g) => (
                <option key={g.value} value={g.value}>
                  {g.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className={labelClass}>utm_source</label>
            <select className={inputClass} value={filters.utm_source ?? ""} onChange={(e) => set("utm_source", e.target.value)}>
              <option value="">Все</option>
              {utmSources.map((s) => (
                <option key={s.id} value={s.code}>
                  {s.code}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className={labelClass}>utm_medium</label>
            <select className={inputClass} value={filters.utm_medium ?? ""} onChange={(e) => set("utm_medium", e.target.value)}>
              <option value="">Все</option>
              {utmMediums.map((m) => (
                <option key={m.id} value={m.code}>
                  {m.code}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className={labelClass}>Тип назначения</label>
            <select className={inputClass} value={filters.link_type ?? ""} onChange={(e) => set("link_type", e.target.value)}>
              {LINK_TYPES.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className={labelClass}>utm_campaign</label>
            <input className={inputClass} value={filters.utm_campaign ?? ""} onChange={(e) => set("utm_campaign", e.target.value)} />
          </div>
          <div>
            <label className={labelClass}>destination содержит</label>
            <input className={inputClass} value={filters.destination ?? ""} onChange={(e) => set("destination", e.target.value)} />
          </div>
        </div>

        <div className="mt-4 flex items-center gap-3">
          <button
            type="button"
            onClick={() => marketingApi.downloadStatsCsv(filters)}
            className="rounded-lg bg-[#1c1c1e] px-4 py-2 text-sm font-medium text-white transition hover:bg-[#333]"
          >
            Выгрузить CSV
          </button>
          {loading && <span className="text-sm text-gray-400">Загрузка...</span>}
        </div>
      </div>

      <div className="overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-50 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">
              <th className="px-4 py-3">{groupLabel}</th>
              <th className="px-4 py-3">Клики</th>
            </tr>
          </thead>
          <tbody>
            {data?.rows.length === 0 && (
              <tr>
                <td colSpan={2} className="px-4 py-6 text-center text-gray-400">
                  Нет данных за выбранный период/фильтры.
                </td>
              </tr>
            )}
            {data?.rows.map((row, i) => (
              <tr key={i} className="border-t border-gray-100 hover:bg-gray-50">
                <td className="break-all px-4 py-2.5">{row.group_value}</td>
                <td className="px-4 py-2.5 font-medium">{row.clicks}</td>
              </tr>
            ))}
          </tbody>
        </table>

        {data && data.total_pages > 1 && (
          <div className="flex items-center justify-center gap-4 border-t border-gray-100 px-4 py-3">
            <button
              disabled={data.page <= 1}
              onClick={() => set("page", data.page - 1)}
              className="rounded-md px-3 py-1.5 text-sm font-medium text-gray-600 hover:bg-gray-100 disabled:opacity-30"
            >
              ← Назад
            </button>
            <span className="text-sm text-gray-500">
              Страница {data.page} из {data.total_pages}
            </span>
            <button
              disabled={data.page >= data.total_pages}
              onClick={() => set("page", data.page + 1)}
              className="rounded-md px-3 py-1.5 text-sm font-medium text-gray-600 hover:bg-gray-100 disabled:opacity-30"
            >
              Вперёд →
            </button>
          </div>
        )}
      </div>

      <div className="text-right text-sm font-semibold text-gray-600">
        Всего кликов (без ботов-превьюеров): {data?.total_clicks ?? 0}
      </div>
    </div>
  );
}
