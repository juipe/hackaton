/**
 * Money formatting and parsing.
 *
 * Every amount in the app is an integer number of minor units (kopecks). Arithmetic
 * stays in integers; the only division happens at the moment of display, which is
 * why no rounding error can accumulate in the UI.
 *
 * The product is rouble-only. The `currency` arguments stay in the signatures for
 * call-site compatibility, but the output is always the same: Russian typography,
 * a non-breaking space between digit groups, a comma before the kopecks and the
 * `₽` sign after the number, again behind a non-breaking space.
 */

export const DEFAULT_CURRENCY = "RUB";

/** U+00A0. Nothing in an amount is ever allowed to wrap away from its number. */
const NBSP = "\u00A0";

const RUBLE_SIGN = "₽";

/** U+2212 MINUS SIGN — в макете у крупных чисел стоит именно он, а не дефис. */
const MINUS_SIGN = "−";

/** Always `₽` — the app knows exactly one currency. */
export function currencySymbol(_currency?: string): string {
  return RUBLE_SIGN;
}

/** `1234567` → `1 234 567`, grouped with non-breaking spaces. */
function groupDigits(major: number): string {
  return String(major).replace(/\B(?=(\d{3})+(?!\d))/g, NBSP);
}

/** `6` → `6`, `1.234` → `1,2`: one decimal, dropped when it is zero. */
function compactNumber(value: number): string {
  const text = value.toFixed(1);
  return text.endsWith(".0") ? text.slice(0, -2) : text.replace(".", ",");
}

/** `123456` → `1 234,56 ₽`. Negatives render as `-1 234,56 ₽`. */
export function formatMoney(cents: number, currency: string = DEFAULT_CURRENCY): string {
  const safe = Number.isFinite(cents) ? Math.trunc(cents) : 0;
  const sign = safe < 0 ? "-" : "";
  const abs = Math.abs(safe);
  const major = Math.trunc(abs / 100);
  const minor = abs % 100;
  const grouped = groupDigits(major);
  return `${sign}${grouped},${String(minor).padStart(2, "0")}${NBSP}${currencySymbol(currency)}`;
}

/** Like {@link formatMoney} but credits carry an explicit `+`. */
export function formatSigned(cents: number, currency: string = DEFAULT_CURRENCY): string {
  if (cents > 0) return `+${formatMoney(cents, currency)}`;
  return formatMoney(cents, currency);
}

/**
 * `3973000` → `39 730 ₽`, с `{ signed: true }` → `+39 730 ₽`.
 *
 * Копейки здесь — шум: функция для мест, где число стоит в тесной строке
 * (баланс группы в сайдбаре, центр доната) и читается беглым взглядом.
 * Минус — типографский U+2212, как в макете: дефис рядом с крупной
 * цифрой выглядит обрубком. `signed` управляет только плюсом у положительных.
 */
export function formatMoneyRounded(
  cents: number,
  opts?: { signed?: boolean },
): string {
  const safe = Number.isFinite(cents) ? Math.trunc(cents) : 0;
  const major = Math.round(Math.abs(safe) / 100);
  // Округление может съесть весь остаток (49 коп. → 0 ₽), и тогда знак
  // при нуле читался бы как ошибка: «−0 ₽».
  if (major === 0) return `0${NBSP}${RUBLE_SIGN}`;
  const sign = safe < 0 ? MINUS_SIGN : opts?.signed ? "+" : "";
  return `${sign}${groupDigits(major)}${NBSP}${RUBLE_SIGN}`;
}

/** Amount without the currency sign and without grouping, for `<input>` fields. */
export function formatAmount(cents: number): string {
  const safe = Number.isFinite(cents) ? Math.trunc(cents) : 0;
  const sign = safe < 0 ? "-" : "";
  const abs = Math.abs(safe);
  return `${sign}${Math.trunc(abs / 100)},${String(abs % 100).padStart(2, "0")}`;
}

/** Compact form for chart axes: `540 ₽`, `1,2 тыс ₽`, `6 млн ₽`. */
export function formatCompact(cents: number, currency: string = DEFAULT_CURRENCY): string {
  const safe = Number.isFinite(cents) ? Math.trunc(cents) : 0;
  const sign = safe < 0 ? "-" : "";
  const symbol = currencySymbol(currency);
  const major = Math.trunc(Math.abs(safe) / 100);
  // Compare the rounded value against the threshold, not the raw one: 999 999 ₽
  // rounds to a single decimal as 1000,0 thousand, and that has to read `1 млн ₽`.
  const thousands = Math.round(major / 100) / 10;
  if (thousands >= 1_000) {
    return `${sign}${compactNumber(major / 1_000_000)}${NBSP}млн${NBSP}${symbol}`;
  }
  if (major >= 1_000) {
    return `${sign}${compactNumber(thousands)}${NBSP}тыс${NBSP}${symbol}`;
  }
  return `${sign}${groupDigits(major)}${NBSP}${symbol}`;
}

/**
 * `"1 234,56"` → `123456`. Understands what a Russian keyboard actually produces:
 * a comma for the decimals, ordinary or non-breaking spaces between digit groups
 * and a stray `₽` anywhere in the string. Returns `null` for anything else.
 */
export function parseAmountToCents(text: string): number | null {
  const cleaned = (text ?? "")
    .replace(/₽/g, "")
    .replace(/\s/g, "")
    .replace(/,/g, ".");
  if (!cleaned) return null;
  if (!/^-?\d*\.?\d*$/.test(cleaned)) return null;
  const [wholePart, fracPart = ""] = cleaned.replace("-", "").split(".");
  if (!wholePart && !fracPart) return null;
  const whole = wholePart ? Number.parseInt(wholePart, 10) : 0;
  // Pad or truncate to exactly two decimals, then round the third digit half-up.
  const frac2 = fracPart.slice(0, 2).padEnd(2, "0");
  const third = fracPart.charAt(2);
  let cents = whole * 100 + Number.parseInt(frac2, 10);
  if (third && Number.parseInt(third, 10) >= 5) cents += 1;
  if (!Number.isFinite(cents)) return null;
  return cleaned.startsWith("-") ? -cents : cents;
}

/** Cents → the string an `<input>` should show while editing. */
export function centsToInput(cents: number | null | undefined): string {
  if (cents === null || cents === undefined || !Number.isFinite(cents)) return "";
  return formatAmount(cents);
}

/** Tailwind class for a balance, by sign. */
export function balanceToneClass(cents: number): string {
  if (cents > 0) return "text-positive";
  if (cents < 0) return "text-negative";
  return "text-muted-foreground";
}

/**
 * Split `cents` across `count` people the way the backend's `equal` mode does:
 * base amount each, leftover kopecks handed out one at a time in order. Used only
 * for the live preview in the expense form — the server recomputes authoritatively.
 */
export function splitEqually(cents: number, count: number): number[] {
  if (count <= 0) return [];
  const base = Math.floor(cents / count);
  const remainder = cents - base * count;
  return Array.from({ length: count }, (_, index) => base + (index < remainder ? 1 : 0));
}

/**
 * Largest-remainder distribution, mirroring the backend's `_distribute`. Weights
 * are percentages or share counts; the result always sums to exactly `cents`.
 */
export function distributeByWeight(cents: number, weights: number[]): number[] {
  const total = weights.reduce((sum, weight) => sum + weight, 0);
  if (total <= 0) return weights.map(() => 0);
  const raw = weights.map((weight) => (cents * weight) / total);
  const floors = raw.map((value) => Math.floor(value));
  let leftover = cents - floors.reduce((sum, value) => sum + value, 0);
  const order = raw
    .map((value, index) => ({ index, remainder: value - Math.floor(value) }))
    .sort((a, b) => b.remainder - a.remainder || a.index - b.index);
  const result = [...floors];
  for (const { index } of order) {
    if (leftover <= 0) break;
    result[index] += 1;
    leftover -= 1;
  }
  return result;
}
