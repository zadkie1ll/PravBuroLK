import { FormEvent, useEffect, useState } from "react";
import {
  BotBlockItem,
  CreateMarketingLinkResponse,
  DictionaryItem,
  KnownValuesResponse,
  marketingApi,
} from "../api/client";

const inputClass =
  "mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-[#1c1c1e] shadow-sm focus:border-gray-500 focus:outline-none focus:ring-1 focus:ring-gray-500";
const labelClass = "block text-sm font-medium text-gray-700";
const hintClass = "mt-1 text-xs text-gray-500";

export function CreateLinkPage() {
  const [utmSources, setUtmSources] = useState<DictionaryItem[]>([]);
  const [utmMediums, setUtmMediums] = useState<DictionaryItem[]>([]);
  const [botBlocks, setBotBlocks] = useState<BotBlockItem[]>([]);
  const [known, setKnown] = useState<KnownValuesResponse>({ campaigns: [], contents: [], terms: [] });

  const [linkType, setLinkType] = useState<"site" | "bot" | "other">("site");
  const [destination, setDestination] = useState("");
  const [utmSourceId, setUtmSourceId] = useState<number | "">("");
  const [utmMediumId, setUtmMediumId] = useState<number | "">("");
  const [botBlockId, setBotBlockId] = useState<number | "">("");
  const [campaign, setCampaign] = useState("");
  const [content, setContent] = useState("");
  const [term, setTerm] = useState("");

  const [errors, setErrors] = useState<string[]>([]);
  const [result, setResult] = useState<CreateMarketingLinkResponse | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    marketingApi.dictionaries().then((d) => {
      setUtmSources(d.utm_sources);
      setUtmMediums(d.utm_mediums);
      setBotBlocks(d.bot_blocks);
      if (d.utm_sources[0]) setUtmSourceId(d.utm_sources[0].id);
      if (d.utm_mediums[0]) setUtmMediumId(d.utm_mediums[0].id);
      if (d.bot_blocks[0]) setBotBlockId(d.bot_blocks[0].id);
    });
    marketingApi.knownValues().then(setKnown);
  }, []);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setErrors([]);
    setResult(null);
    setSubmitting(true);
    try {
      const response = await marketingApi.createLink({
        link_type: linkType,
        destination: linkType === "bot" ? undefined : destination,
        utm_source_id: Number(utmSourceId),
        utm_medium_id: Number(utmMediumId),
        utm_campaign: campaign,
        utm_content: content,
        utm_term: term,
        bot_block_id: linkType === "bot" ? Number(botBlockId) : undefined,
      });
      setResult(response);
      marketingApi.knownValues().then(setKnown);
    } catch (err) {
      setErrors([err instanceof Error ? err.message : "Ошибка создания ссылки"]);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto max-w-xl">
      <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
        <h2 className="mb-6 text-lg font-semibold">Создание ссылки с разметкой</h2>

        {errors.map((err, i) => (
          <p key={i} className="mb-3 rounded-lg bg-red-50 p-3 text-sm text-red-600">
            {err}
          </p>
        ))}

        {result && (
          <div
            className={`mb-6 rounded-lg border p-4 text-sm ${
              result.is_existing ? "border-amber-300 bg-amber-50" : "border-green-300 bg-green-50"
            }`}
          >
            <strong>{result.is_existing ? "Такая ссылка уже существует:" : "Ссылка создана:"}</strong>
            <div className="mt-1 break-all font-mono text-xs">{result.link.public_link}</div>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className={labelClass}>Тип назначения</label>
            <select
              className={inputClass}
              value={linkType}
              onChange={(e) => setLinkType(e.target.value as "site" | "bot" | "other")}
            >
              <option value="site">Сайт (классическая UTM)</option>
              <option value="bot">Telegram-бот</option>
              <option value="other">Прочие площадки</option>
            </select>
          </div>

          {linkType !== "bot" && (
            <div>
              <label className={labelClass}>Целевая ссылка</label>
              <input
                type="url"
                required
                placeholder="https://prav-buro.com/"
                value={destination}
                onChange={(e) => setDestination(e.target.value)}
                className={inputClass}
              />
            </div>
          )}

          <div>
            <label className={labelClass}>utm_source</label>
            <select className={inputClass} value={utmSourceId} onChange={(e) => setUtmSourceId(Number(e.target.value))}>
              {utmSources.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.code}
                </option>
              ))}
            </select>
            <p className={hintClass}>Указывает на название источника трафика.</p>
          </div>

          <div>
            <label className={labelClass}>utm_medium</label>
            <select className={inputClass} value={utmMediumId} onChange={(e) => setUtmMediumId(Number(e.target.value))}>
              {utmMediums.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.code}
                </option>
              ))}
            </select>
            <p className={hintClass}>cpc — платный трафик, organic — бесплатный.</p>
          </div>

          {linkType === "bot" && (
            <div>
              <label className={labelClass}>Блок бота</label>
              <select className={inputClass} value={botBlockId} onChange={(e) => setBotBlockId(Number(e.target.value))}>
                {botBlocks.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.key} — {b.title}
                  </option>
                ))}
              </select>
            </div>
          )}

          <div>
            <label className={labelClass}>utm_campaign</label>
            <input
              type="text"
              required
              pattern="[a-z0-9\-]+"
              list="campaign-suggestions"
              value={campaign}
              onChange={(e) => setCampaign(e.target.value.toLowerCase())}
              className={inputClass}
            />
            <datalist id="campaign-suggestions">
              {known.campaigns.map((c) => (
                <option key={c} value={c} />
              ))}
            </datalist>
            <p className={hintClass}>Тема кампании/видео/крео. Латиница, цифры, дефис — без подчёркивания.</p>
          </div>

          <div>
            <label className={labelClass}>utm_content (необязательно)</label>
            <input
              type="text"
              pattern="[a-z0-9\-]*"
              list="content-suggestions"
              value={content}
              onChange={(e) => setContent(e.target.value.toLowerCase())}
              className={inputClass}
            />
            <datalist id="content-suggestions">
              {known.contents.map((c) => (
                <option key={c} value={c} />
              ))}
            </datalist>
          </div>

          <div>
            <label className={labelClass}>utm_term (необязательно)</label>
            <input
              type="text"
              pattern="[a-z0-9\-]*"
              list="term-suggestions"
              value={term}
              onChange={(e) => setTerm(e.target.value.toLowerCase())}
              className={inputClass}
            />
            <datalist id="term-suggestions">
              {known.terms.map((t) => (
                <option key={t} value={t} />
              ))}
            </datalist>
          </div>

          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded-lg bg-[#1c1c1e] px-4 py-2.5 text-sm font-medium text-white transition hover:bg-[#333] disabled:opacity-50"
          >
            {submitting ? "Создаём..." : "Создать ссылку"}
          </button>
        </form>
      </div>
    </div>
  );
}
