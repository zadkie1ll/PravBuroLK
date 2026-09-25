export interface ReportFields {
  client: string;
  // Дата/время консультации и два поля рассрочки ниже пишет другой процесс
  // (документы/договор) — на этой странице только показываются, не редактируются.
  date: string;
  time: string;
  property: string;
  income: string;
  transactions: string;
  marriage: string;
  children: string;
  contract: string;
  debt: string;
  cost: string;
  installment: string;
  months: string;
  firstPayment: string;
  // Полей под это пока нет в Bitrix (см. backend/app/config.py) — заполняются
  // на странице, но при сохранении пока никуда не улетают.
  priority: string;
  summary: string;
  currentPayment: string;
  included: string;
  extra: string;
  nextStep: string;
  nextDate: string;
  documents: string;
}

/** Сырые числа для живого предпросмотра "Итого по графику" — считается на
 * фронте от текущего (возможно ещё не сохранённого) fields.cost, а не только
 * один раз на сервере при загрузке страницы. */
export interface ReportComputed {
  bonusAmount: number;
  discountAmount: number;
}

export interface ReportManager {
  name: string | null;
  contact: string | null;
  role: string | null;
  photoUrl: string | null;
}

export interface ReportLinks {
  chat: string;
  telegram: string;
  vk: string;
  youtube: string;
  yandexMaps: string;
}

export interface ReportResponse {
  dealId: string;
  fields: ReportFields;
  computed: ReportComputed;
  manager: ReportManager;
  links: ReportLinks;
}
