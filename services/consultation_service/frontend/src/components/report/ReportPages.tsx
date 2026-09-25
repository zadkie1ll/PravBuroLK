import type { ReportComputed, ReportFields, ReportLinks, ReportManager } from "../../types";
import { EditableField } from "./EditableField";
import { formatAmount, formatMoney, parseAmount } from "./format";
import {
  CABINET_TEXT,
  CLOSING_TEXT,
  COMMUNITY_TEXT,
  STAGES,
  TIMING_NOTE_TEXT,
} from "./staticContent";

interface ReportPagesProps {
  fields: ReportFields;
  computed: ReportComputed;
  manager: ReportManager;
  links: ReportLinks;
  editable: boolean;
  onFieldChange: (key: keyof ReportFields, value: string) => void;
}

function Brand() {
  return (
    <div className="brand">
      <img src="/logo.png" alt="ПРАВБЮРО" />
    </div>
  );
}

function PageFooter({ clientName, index, total }: { clientName: string; index: number; total: number }) {
  return (
    <footer className="footer">
      <span className="foot-client">{clientName.trim() || "Итоги консультации"}</span>
      <span className="page-number">
        {String(index).padStart(2, "0")} / {String(total).padStart(2, "0")}
      </span>
    </footer>
  );
}

function Title({ eyebrow, heading, lead }: { eyebrow: string; heading: React.ReactNode; lead?: string }) {
  return (
    <div className="title">
      <div className="eyebrow">{eyebrow}</div>
      <h1>{heading}</h1>
      {lead ? <p className="lead">{lead}</p> : null}
    </div>
  );
}

const FACT_ROWS: Array<[keyof ReportFields, string]> = [
  ["property", "Имущество"],
  ["income", "Доход"],
  ["transactions", "Сделки"],
  ["marriage", "Семейное положение"],
  ["children", "Дети"],
  ["contract", "Договор"],
];

function Facts({ fields, editable, onFieldChange }: Pick<ReportPagesProps, "fields" | "editable" | "onFieldChange">) {
  return (
    <div className="facts">
      {FACT_ROWS.map(([key, label]) => (
        <div className="fact" key={key}>
          <div className="label">{label}</div>
          <div className="value">
            <EditableField
              value={fields[key]}
              editable={editable}
              onChange={(v) => onFieldChange(key, v)}
              placeholder="Не уточнено"
            />
          </div>
        </div>
      ))}
    </div>
  );
}

function Profile({ manager }: { manager: ReportManager }) {
  return (
    <div className="profile">
      {manager.photoUrl ? <img src={manager.photoUrl} alt="Фото специалиста" /> : null}
      <div>
        <div className="role">{manager.role || "Ваш специалист"}</div>
        <div className="name">{manager.name || "Имя специалиста"}</div>
        <div className="contact">{manager.contact || "Контакт уточняется"}</div>
      </div>
    </div>
  );
}

function Hero({ value }: { value: string }) {
  return (
    <div className="financial-hero">
      <div className="label">Общая сумма задолженности</div>
      <div className="amount">{value.trim() ? formatMoney(value) : <span className="placeholder">Сумма не указана</span>}</div>
    </div>
  );
}

function Metrics({ fields, editable, onFieldChange }: Pick<ReportPagesProps, "fields" | "editable" | "onFieldChange">) {
  return (
    <div className="metrics">
      <div className="metric">
        <div className="label">Стоимость услуг</div>
        <div className="amount">
          <EditableField
            value={fields.cost}
            editable={editable}
            onChange={(v) => onFieldChange("cost", v)}
            money
            placeholder="Сумма не указана"
          />
        </div>
      </div>
      <div className="metric">
        <div className="label">
          Ежемесячный платёж
          <br />
          по рассрочке
        </div>
        <div className="amount">
          <EditableField
            value={fields.installment}
            editable={editable}
            onChange={(v) => onFieldChange("installment", v)}
            money
            placeholder="Сумма не указана"
          />
        </div>
      </div>
    </div>
  );
}

/** Только показ — эти три поля пишет бот/менеджер при оформлении договора, не эта страница. */
function ReadOnlyTerm({ label, value }: { label: string; value: string }) {
  return (
    <div className="term">
      <span className="label">{label}</span>
      <span className="value">{value.trim() || <span className="placeholder">Уточняется</span>}</span>
    </div>
  );
}

function Term({
  label,
  value,
  editable,
  onChange,
  money,
}: {
  label: string;
  value: string;
  editable: boolean;
  onChange: (v: string) => void;
  money?: boolean;
}) {
  return (
    <div className="term">
      <span className="label">{label}</span>
      <span className="value">
        <EditableField value={value} editable={editable} onChange={onChange} money={money} />
      </span>
    </div>
  );
}

/** Полей под "В стоимость входит"/"Отдельные расходы" пока нет в Bitrix (см.
 * config.py: PENDING_BITRIX_FIELD_KEYS) — заполняются, но не сохраняются. Скрыты
 * в read-only режиме, если пусто, чтобы пустая заглушка не летела в PDF. */
function OptionalNote({
  value,
  title,
  editable,
  onChange,
}: {
  value: string;
  title: string;
  editable: boolean;
  onChange: (v: string) => void;
}) {
  if (!editable && !value.trim()) return null;
  return (
    <div className="note">
      <div className="section-title">{title}</div>
      <p>
        <EditableField value={value} editable={editable} onChange={onChange} multiline />
      </p>
    </div>
  );
}

function FinancialTerms({ fields, computed, editable, onFieldChange }: Pick<ReportPagesProps, "fields" | "computed" | "editable" | "onFieldChange">) {
  // Живой предпросмотр: пересчитывается сразу при вводе "Стоимость услуг", а не
  // только после сохранения — это единственное реально вычисляемое значение
  // в этом отчёте (остальное либо сырой ввод, либо снимок из другого процесса).
  const costNow = parseAmount(fields.cost);
  const total = costNow - computed.discountAmount + computed.bonusAmount;
  const totalDisplay = fields.cost.trim() ? formatAmount(total) : "";

  return (
    <div className="term-list">
      <ReadOnlyTerm label="Срок рассрочки" value={fields.months} />
      <ReadOnlyTerm label="Первый платёж и дата" value={fields.firstPayment} />
      <ReadOnlyTerm label="Итого по графику" value={totalDisplay} />
      {editable || fields.currentPayment.trim() ? (
        <Term
          label="Текущий платёж по долгам"
          value={fields.currentPayment}
          editable={editable}
          onChange={(v) => onFieldChange("currentPayment", v)}
          money
        />
      ) : null}
      <OptionalNote
        title="В стоимость входит"
        value={fields.included}
        editable={editable}
        onChange={(v) => onFieldChange("included", v)}
      />
      <OptionalNote title="Отдельные расходы" value={fields.extra} editable={editable} onChange={(v) => onFieldChange("extra", v)} />
    </div>
  );
}

function NextActions({ fields, editable, onFieldChange }: Pick<ReportPagesProps, "fields" | "editable" | "onFieldChange">) {
  const rows: Array<[keyof ReportFields, string, string]> = [
    ["nextStep", "Следующий шаг", "Согласовать со специалистом"],
    ["nextDate", "Дата контакта", "Уточняется"],
  ];
  return (
    <div className="action-block">
      <div className="section-title">Дальнейшие действия</div>
      {rows.map(([key, label, placeholder]) => (
        <div className="action-row" key={key}>
          <div className="label">{label}</div>
          <div className="value">
            <EditableField value={fields[key]} editable={editable} onChange={(v) => onFieldChange(key, v)} placeholder={placeholder} />
          </div>
        </div>
      ))}
      {editable || fields.documents.trim() ? (
        <div className="action-row">
          <div className="label">Предоставить</div>
          <div className="value">
            <EditableField value={fields.documents} editable={editable} onChange={(v) => onFieldChange("documents", v)} multiline />
          </div>
        </div>
      ) : null}
    </div>
  );
}

function Steps({ indices }: { indices: number[] }) {
  return (
    <div className="steps">
      {indices.map((i) => {
        const stage = STAGES[i];
        return (
          <div className="step" key={i}>
            <div className="step-no">{String(i + 1).padStart(2, "0")}</div>
            <div>
              <div className="step-title">
                <h3>{stage.title}</h3>
              </div>
              {stage.timing ? <span className="timing">{stage.timing}</span> : null}
              <p>{stage.body}</p>
              {stage.extra ? <p className="subline">{stage.extra}</p> : null}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function Support({ links }: { links: ReportLinks }) {
  const showQr = links.chat === "https://t.me/+0cxGWcMqMPY2Yzky";
  return (
    <div className="support" style={!showQr ? { gridTemplateColumns: "1fr" } : undefined}>
      <div>
        <h3>Чат поддержки</h3>
        <p>{COMMUNITY_TEXT}</p>
        <p>
          <a href={links.chat} target="_blank" rel="noopener noreferrer">
            Перейти в чат поддержки ↗
          </a>
        </p>
      </div>
      {showQr ? (
        <div className="qr">
          <a href={links.chat} target="_blank" rel="noopener noreferrer">
            <img src="/support-chat-qr.svg" alt="QR-код чата поддержки" />
            Открыть чат
          </a>
        </div>
      ) : null}
    </div>
  );
}

function Social({ links }: { links: ReportLinks }) {
  const items: Array<[string, string]> = [
    [links.telegram, "Telegram ↗"],
    [links.vk, "ВКонтакте ↗"],
    [links.youtube, "YouTube ↗"],
    [links.yandexMaps, "Яндекс.Карты ↗"],
  ];
  return (
    <div className="section">
      <div className="section-title">О компании</div>
      <div className="socials">
        {items
          .filter(([url]) => Boolean(url))
          .map(([url, label]) => (
            <a href={url} target="_blank" rel="noopener noreferrer" key={label}>
              {label}
            </a>
          ))}
      </div>
    </div>
  );
}

function Closing() {
  return (
    <div className="closing">
      <h3>Решение в вашем темпе</h3>
      <p>{CLOSING_TEXT}</p>
    </div>
  );
}

function Cabinet() {
  return (
    <div className="section">
      <div className="section-title">Личный кабинет</div>
      <p>{CABINET_TEXT}</p>
    </div>
  );
}

function TimingNote() {
  return <div className="timing-note">{TIMING_NOTE_TEXT}</div>;
}

export function ReportPages({ fields, computed, manager, links, editable, onFieldChange }: ReportPagesProps) {
  const totalPages = 5;
  const clientName = fields.client;

  return (
    <div className="report-viewer">
      {/* Страница 1 — Ваша ситуация */}
      <section className="page">
        <div className="page-content">
          <Brand />
          <Title eyebrow="Итоги консультации" heading="Ваша ситуация" />
          <div className="client-name">
            <EditableField value={fields.client} editable={editable} onChange={(v) => onFieldChange("client", v)} placeholder="Имя клиента" />
          </div>
          <div className="byline">
            {fields.date || "Дата консультации"}
            {fields.time ? ` · ${fields.time}` : ""}
          </div>
          <Profile manager={manager} />
          <Facts fields={fields} editable={editable} onFieldChange={onFieldChange} />
          <OptionalNote title="Ваш вопрос" value={fields.priority} editable={editable} onChange={(v) => onFieldChange("priority", v)} />
          <OptionalNote title="Итог консультации" value={fields.summary} editable={editable} onChange={(v) => onFieldChange("summary", v)} />
        </div>
        <PageFooter clientName={clientName} index={1} total={totalPages} />
      </section>

      {/* Страница 2 — Финансовые условия */}
      <section className="page">
        <div className="page-content">
          <Brand />
          <Title eyebrow="Финансовые условия" heading={<>Стоимость<br />и платежи</>} />
          <Hero value={fields.debt} />
          <Metrics fields={fields} editable={editable} onFieldChange={onFieldChange} />
          <FinancialTerms fields={fields} computed={computed} editable={editable} onFieldChange={onFieldChange} />
        </div>
        <PageFooter clientName={clientName} index={2} total={totalPages} />
      </section>

      {/* Страница 3 — План работы 01-04 */}
      <section className="page process-page">
        <div className="page-content">
          <Brand />
          <Title eyebrow="План работы / 01-04" heading="Начало работы" />
          <Steps indices={[0, 1, 2, 3]} />
        </div>
        <PageFooter clientName={clientName} index={3} total={totalPages} />
      </section>

      {/* Страница 4 — План работы 05-07 */}
      <section className="page process-page">
        <div className="page-content">
          <Brand />
          <Title eyebrow="План работы / 05-07" heading="Суд и завершение" />
          <Steps indices={[4, 5, 6]} />
          <Cabinet />
          <TimingNote />
        </div>
        <PageFooter clientName={clientName} index={4} total={totalPages} />
      </section>

      {/* Страница 5 — После консультации */}
      <section className="page">
        <div className="page-content">
          <Brand />
          <Title eyebrow="После консультации" heading="Мы на связи" />
          <NextActions fields={fields} editable={editable} onFieldChange={onFieldChange} />
          <Support links={links} />
          <Social links={links} />
          <Closing />
        </div>
        <PageFooter clientName={clientName} index={5} total={totalPages} />
      </section>
    </div>
  );
}
