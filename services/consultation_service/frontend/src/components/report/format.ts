/** Bitrix money-поля отдают "800000|RUB" — валюту отбрасываем, оставляем число. */
export function parseAmount(raw: string): number {
  const withoutCurrency = raw.split("|", 1)[0];
  const cleaned = withoutCurrency.replace(/[\s ₽]/g, "").replace(",", ".");
  const n = Number(cleaned);
  return Number.isFinite(n) ? n : 0;
}

export function formatMoney(raw: string): string {
  const withoutCurrency = raw.split("|", 1)[0];
  const cleaned = withoutCurrency.replace(/[\s ₽]/g, "").replace(",", ".");
  const n = Number(cleaned);
  if (!cleaned || !Number.isFinite(n) || n < 0) return raw;
  return new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 2 }).format(n) + " ₽";
}

export function formatAmount(amount: number): string {
  return new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 2 }).format(amount) + " ₽";
}

export function isValidHttpUrl(value: string): boolean {
  try {
    const u = new URL(value);
    return u.protocol === "https:" || u.protocol === "http:";
  } catch {
    return false;
  }
}
