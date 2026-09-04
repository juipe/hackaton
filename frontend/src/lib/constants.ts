import type { DashboardPeriod, SplitMode } from "@/types/api";

export const APP_NAME = "Складчина";
export const APP_TAGLINE = "Общие расходы — поровну и без споров";

/** The product knows exactly one currency; re-exported so call sites have one import. */
export { DEFAULT_CURRENCY } from "@/lib/money";

export const SPLIT_MODES: { value: SplitMode; label: string; hint: string }[] = [
  { value: "equal", label: "Поровну", hint: "Все платят одинаково" },
  { value: "exact", label: "Точные суммы", hint: "Указать сумму для каждого" },
  { value: "percentage", label: "Проценты", hint: "Сумма долей — 100%" },
  { value: "shares", label: "Доли", hint: "Например, 2 доли на пару" },
];

export const PERIODS: { value: DashboardPeriod; label: string }[] = [
  { value: "all", label: "За всё время" },
  { value: "this_month", label: "Этот месяц" },
  { value: "last_month", label: "Прошлый месяц" },
  { value: "last_3_months", label: "Последние 3 месяца" },
  { value: "custom", label: "Свой период" },
];

/**
 * Chart palette. The brand green leads; the rest are ordered so neighbouring
 * slices stay distinguishable. These are categories, not signs — the balance
 * colours live in the --positive / --negative tokens and are used nowhere here.
 */
export const CHART_COLORS = [
  "#21A038",
  "#0F8A6A",
  "#2E9BD6",
  "#7B61FF",
  "#F5A623",
  "#E5533D",
  "#5CC35A",
  "#0E7490",
  "#B0679B",
  "#8D9F3C",
  "#C77D22",
  "#64748B",
] as const;

/** Команда хакатона: пять демо-аккаунтов, один пароль на всех. */
export const DEMO_ACCOUNTS = [
  { email: "olya@skladchina.ru", name: "Оля" },
  { email: "sasha@skladchina.ru", name: "Саша" },
  { email: "kostya@skladchina.ru", name: "Костя" },
  { email: "maksim@skladchina.ru", name: "Максим" },
  { email: "zhora@skladchina.ru", name: "Жора" },
] as const;

export const DEMO_PASSWORD = "Demo1234!";
