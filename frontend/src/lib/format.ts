/** Date and text formatting helpers shared across the app. */

const DAY = 24 * 60 * 60 * 1000;

export function parseDate(value: string): Date {
  return new Date(value);
}

/**
 * `ru-RU` appends ` г.` to a full date and a dot to an abbreviated month. Both are
 * correct in prose and pure noise in an interface, so they are trimmed here once
 * instead of at twenty call sites.
 */
function trimRuDateTail(text: string): string {
  // The leading \s+ is load-bearing: without it the pattern also eats the "г." at
  // the end of "14 авг.", and August turns into "14 ав".
  return text.replace(/\s+г\.\s*$/, "");
}

/** `14 августа 2026` */
export function formatDate(value: string | Date): string {
  const date = typeof value === "string" ? parseDate(value) : value;
  if (Number.isNaN(date.getTime())) return "—";
  return trimRuDateTail(
    date.toLocaleDateString("ru-RU", {
      day: "numeric",
      month: "long",
      year: "numeric",
    }),
  );
}

/** `14 авг` — for dense lists; the year appears only when it is not the current one. */
export function formatDateShort(value: string | Date): string {
  const date = typeof value === "string" ? parseDate(value) : value;
  if (Number.isNaN(date.getTime())) return "—";
  const sameYear = date.getFullYear() === new Date().getFullYear();
  const text = date.toLocaleDateString("ru-RU", {
    day: "numeric",
    month: "short",
    ...(sameYear ? {} : { year: "numeric" }),
  });
  return trimRuDateTail(text).replace(/\./g, "");
}

/** `только что`, `вчера`, `3 дня назад`, then falls back to a date. */
export function formatRelative(value: string | Date): string {
  const date = typeof value === "string" ? parseDate(value) : value;
  if (Number.isNaN(date.getTime())) return "—";
  const diff = Date.now() - date.getTime();
  if (diff < 60_000) return "только что";
  if (diff < 3_600_000) {
    const minutes = Math.floor(diff / 60_000);
    return `${minutes} мин назад`;
  }
  if (diff < DAY) {
    const hours = Math.floor(diff / 3_600_000);
    return `${hours} ч назад`;
  }
  const days = Math.floor(diff / DAY);
  if (days === 1) return "вчера";
  if (days < 7) return `${plural(days, "день", "дня", "дней")} назад`;
  return formatDateShort(date);
}

/**
 * Заголовок дня в списке расходов: «Сегодня», «Вчера», иначе «1 сентября».
 *
 * Сравниваются календарные дни, а не разница в часах: расход, созданный
 * в 23:50, в 00:10 уже «Вчера», хотя ему двадцать минут. Год появляется
 * только у дат из другого года.
 */
export function formatDayHeading(value: string | Date): string {
  const date = typeof value === "string" ? parseDate(value) : value;
  if (Number.isNaN(date.getTime())) return "—";

  const now = new Date();
  const startOfDay = (d: Date): number =>
    new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  const days = Math.round((startOfDay(now) - startOfDay(date)) / DAY);
  if (days === 0) return "Сегодня";
  if (days === 1) return "Вчера";

  const sameYear = date.getFullYear() === now.getFullYear();
  return trimRuDateTail(
    date.toLocaleDateString("ru-RU", {
      day: "numeric",
      month: "long",
      ...(sameYear ? {} : { year: "numeric" }),
    }),
  );
}

/** `2026-08-14`, the value an `<input type="date">` expects. */
export function toDateInputValue(value: string | Date): string {
  const date = typeof value === "string" ? parseDate(value) : value;
  if (Number.isNaN(date.getTime())) return "";
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${date.getFullYear()}-${month}-${day}`;
}

/**
 * A date-only input is a wall-clock day, not an instant. Anchoring it at midday
 * UTC keeps the day from sliding backwards for users west of Greenwich when the
 * server groups expenses into months.
 */
export function dateInputToIso(value: string): string {
  if (!value) return new Date().toISOString();
  return new Date(`${value}T12:00:00Z`).toISOString();
}

export function todayInputValue(): string {
  return toDateInputValue(new Date());
}

/**
 * Russian has three plural forms, and picking the wrong one is the fastest way to
 * make an interface read like a machine translation. The rule is the canonical one:
 * `1, 21, 101` take `one`; `2…4, 22…24` take `few`; everything else — including the
 * whole `11…14` teens block and zero — takes `many`.
 */
export function pluralWord(count: number, one: string, few: string, many: string): string {
  const n = Math.abs(Math.trunc(count));
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return one;
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return few;
  return many;
}

/** `plural(3, "участник", "участника", "участников")` → `3 участника`. */
export function plural(count: number, one: string, few: string, many: string): string {
  return `${count} ${pluralWord(count, one, few, many)}`;
}

export function truncate(text: string, max: number): string {
  if (text.length <= max) return text;
  return `${text.slice(0, Math.max(0, max - 1))}…`;
}

/** «Оля», «Оля и Саша», «Оля, Саша и ещё 2» */
export function joinNames(names: string[], max = 2): string {
  if (names.length === 0) return "";
  if (names.length === 1) return names[0];
  if (names.length <= max) {
    return `${names.slice(0, -1).join(", ")} и ${names[names.length - 1]}`;
  }
  const shown = names.slice(0, max).join(", ");
  const rest = names.length - max;
  return `${shown} и ещё ${rest}`;
}
