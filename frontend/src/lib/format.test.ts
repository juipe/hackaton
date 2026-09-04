import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  dateInputToIso,
  formatDate,
  formatDateShort,
  formatDayHeading,
  formatRelative,
  joinNames,
  plural,
  pluralWord,
  toDateInputValue,
  todayInputValue,
  truncate,
} from "@/lib/format";

/** setup.ts фиксирует зону America/Los_Angeles, то есть локальное время — UTC-7/-8. */

describe("toDateInputValue", () => {
  it("отдаёт локальный календарный день, которого ждёт <input type=date>", () => {
    expect(toDateInputValue(new Date(2026, 7, 14, 9, 30))).toBe("2026-08-14");
  });

  it("дополняет месяц и день нулями", () => {
    expect(toDateInputValue(new Date(2026, 0, 5))).toBe("2026-01-05");
  });

  it("принимает строку ISO", () => {
    expect(toDateInputValue("2026-08-14T12:00:00Z")).toBe("2026-08-14");
  });

  it("возвращает пустую строку, если дату не разобрать", () => {
    expect(toDateInputValue("не дата")).toBe("");
  });
});

describe("dateInputToIso", () => {
  it("привязывает день к полудню UTC", () => {
    expect(dateInputToIso("2026-08-14")).toBe("2026-08-14T12:00:00.000Z");
  });

  it("оставляет момент внутри нужного дня для зон западнее Гринвича", () => {
    // Привязка к полуночи UTC дала бы 13 августа, 17:00 по местному времени,
    // и расход уехал бы не в тот день — а на границе месяца и не в тот месяц.
    const local = new Date(dateInputToIso("2026-08-01"));
    expect(local.getUTCHours()).toBe(12);
    expect(toDateInputValue(local)).toBe("2026-08-01");
  });

  it("делает полный круг с toDateInputValue", () => {
    for (const day of ["2026-01-01", "2026-02-28", "2026-08-14", "2026-12-31"]) {
      expect(toDateInputValue(new Date(dateInputToIso(day)))).toBe(day);
    }
  });

  it("подставляет текущий момент для пустого значения", () => {
    const before = Date.now();
    const iso = dateInputToIso("");
    const parsed = new Date(iso).getTime();
    expect(Number.isNaN(parsed)).toBe(false);
    expect(parsed).toBeGreaterThanOrEqual(before - 1000);
    expect(parsed).toBeLessThanOrEqual(Date.now() + 1000);
  });
});

describe("todayInputValue", () => {
  it("совпадает с сегодняшним локальным днём", () => {
    expect(todayInputValue()).toBe(toDateInputValue(new Date()));
  });
});

describe("formatDate", () => {
  it("пишет дату словами, месяц в родительном падеже", () => {
    expect(formatDate(new Date(2026, 7, 14))).toBe("14 августа 2026");
    expect(formatDate(new Date(2026, 0, 1))).toBe("1 января 2026");
    expect(formatDate(new Date(2025, 11, 31))).toBe("31 декабря 2025");
  });

  it("обрезает хвост « г.», который добавляет локаль", () => {
    expect(formatDate(new Date(2026, 7, 14))).not.toContain("г.");
  });

  it("принимает строку ISO", () => {
    expect(formatDate("2026-08-14T12:00:00Z")).toBe("14 августа 2026");
  });

  it("вместо исключения показывает тире", () => {
    expect(formatDate("ерунда")).toBe("—");
    expect(formatDateShort("ерунда")).toBe("—");
    expect(formatRelative("ерунда")).toBe("—");
  });
});

describe("formatDateShort", () => {
  it("сокращает месяц и убирает точку после него", () => {
    const thisYear = new Date().getFullYear();
    expect(formatDateShort(new Date(thisYear, 7, 14))).toBe("14 авг");
    expect(formatDateShort(new Date(thisYear, 0, 5))).toBe("5 янв");
  });

  it("добавляет год, если он не текущий, и всё равно без точек", () => {
    expect(formatDateShort(new Date(2001, 0, 5))).toBe("5 янв 2001");
    expect(formatDateShort(new Date(2001, 0, 5))).not.toContain(".");
  });
});

describe("formatRelative", () => {
  it("описывает недавние моменты словами", () => {
    expect(formatRelative(new Date())).toBe("только что");
    expect(formatRelative(new Date(Date.now() - 5 * 60_000))).toBe("5 мин назад");
    expect(formatRelative(new Date(Date.now() - 3 * 3_600_000))).toBe("3 ч назад");
    expect(formatRelative(new Date(Date.now() - 26 * 3_600_000))).toBe("вчера");
  });

  it("согласует «день» с числом", () => {
    expect(formatRelative(new Date(Date.now() - 2 * 24 * 3_600_000))).toBe("2 дня назад");
    expect(formatRelative(new Date(Date.now() - 3 * 24 * 3_600_000))).toBe("3 дня назад");
    expect(formatRelative(new Date(Date.now() - 5 * 24 * 3_600_000))).toBe("5 дней назад");
    expect(formatRelative(new Date(Date.now() - 6 * 24 * 3_600_000))).toBe("6 дней назад");
  });

  it("после недели переходит на короткую дату", () => {
    const long = new Date(Date.now() - 30 * 24 * 3_600_000);
    expect(formatRelative(long)).toBe(formatDateShort(long));
  });
});

describe("formatDayHeading", () => {
  /* Заголовок дня считается от «сегодня», поэтому время здесь прибито гвоздями. */
  const NOW = new Date(2026, 8, 4, 10, 0, 0);

  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(NOW);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("сегодняшний день называет словом", () => {
    expect(formatDayHeading(new Date(2026, 8, 4, 10, 0))).toBe("Сегодня");
    expect(formatDayHeading(new Date(2026, 8, 4, 0, 5))).toBe("Сегодня");
    expect(formatDayHeading(new Date(2026, 8, 4, 23, 55))).toBe("Сегодня");
  });

  it("вчерашний — тоже, даже если ему двадцать минут", () => {
    expect(formatDayHeading(new Date(2026, 8, 3, 23, 50))).toBe("Вчера");
    expect(formatDayHeading(new Date(2026, 8, 3, 0, 1))).toBe("Вчера");
  });

  it("остальные дни текущего года — день и месяц в родительном, без года", () => {
    expect(formatDayHeading(new Date(2026, 8, 1, 12, 0))).toBe("1 сентября");
    expect(formatDayHeading(new Date(2026, 0, 14, 12, 0))).toBe("14 января");
  });

  it("дата из другого года получает год и теряет «г.»", () => {
    expect(formatDayHeading(new Date(2025, 11, 31, 12, 0))).toBe("31 декабря 2025");
    expect(formatDayHeading(new Date(2025, 11, 31, 12, 0))).not.toContain("г.");
  });

  it("будущее не выдаётся за «Вчера»", () => {
    expect(formatDayHeading(new Date(2026, 8, 5, 12, 0))).toBe("5 сентября");
  });

  it("понимает ISO-строку и отбивает мусор", () => {
    expect(formatDayHeading("2026-09-04T18:00:00Z")).toBe("Сегодня");
    expect(formatDayHeading("не дата")).toBe("—");
  });
});

describe("pluralWord", () => {
  it("выбирает форму по каноническому русскому правилу", () => {
    const form = (n: number) => pluralWord(n, "участник", "участника", "участников");
    expect(form(0)).toBe("участников");
    expect(form(1)).toBe("участник");
    expect(form(2)).toBe("участника");
    expect(form(5)).toBe("участников");
    expect(form(11)).toBe("участников");
    expect(form(21)).toBe("участник");
    expect(form(22)).toBe("участника");
    expect(form(25)).toBe("участников");
    expect(form(101)).toBe("участник");
    expect(form(111)).toBe("участников");
  });

  it("держит весь блок 11…14 в третьей форме", () => {
    for (const n of [11, 12, 13, 14, 111, 112, 113, 114]) {
      expect(pluralWord(n, "день", "дня", "дней")).toBe("дней");
    }
  });

  it("отдаёт вторую форму для 2…4 вне блока подростков", () => {
    for (const n of [2, 3, 4, 22, 23, 24, 102, 103, 104]) {
      expect(pluralWord(n, "день", "дня", "дней")).toBe("дня");
    }
  });

  it("возвращает только слово, без числа", () => {
    expect(pluralWord(3, "участник", "участника", "участников")).toBe("участника");
  });
});

describe("plural", () => {
  it("склеивает число с согласованным словом", () => {
    expect(plural(0, "участник", "участника", "участников")).toBe("0 участников");
    expect(plural(1, "участник", "участника", "участников")).toBe("1 участник");
    expect(plural(2, "участник", "участника", "участников")).toBe("2 участника");
    expect(plural(3, "участник", "участника", "участников")).toBe("3 участника");
    expect(plural(5, "участник", "участника", "участников")).toBe("5 участников");
    expect(plural(11, "участник", "участника", "участников")).toBe("11 участников");
    expect(plural(21, "участник", "участника", "участников")).toBe("21 участник");
    expect(plural(22, "участник", "участника", "участников")).toBe("22 участника");
    expect(plural(25, "участник", "участника", "участников")).toBe("25 участников");
    expect(plural(101, "участник", "участника", "участников")).toBe("101 участник");
    expect(plural(111, "участник", "участника", "участников")).toBe("111 участников");
  });

  it("работает с другими словами так же", () => {
    expect(plural(1, "расход", "расхода", "расходов")).toBe("1 расход");
    expect(plural(4, "расход", "расхода", "расходов")).toBe("4 расхода");
    expect(plural(14, "расход", "расхода", "расходов")).toBe("14 расходов");
    expect(plural(2, "перевод", "перевода", "переводов")).toBe("2 перевода");
  });
});

describe("truncate", () => {
  it("не трогает короткий текст", () => {
    expect(truncate("Продукты", 20)).toBe("Продукты");
    expect(truncate("абв", 3)).toBe("абв");
  });

  it("режет до лимита вместе с многоточием", () => {
    expect(truncate("Пятёрочка и Мегамарт", 8)).toBe("Пятёроч…");
    expect(truncate("Пятёрочка и Мегамарт", 8)).toHaveLength(8);
    expect(truncate("абвг", 3)).toBe("аб…");
  });

  it("переживает нулевой лимит", () => {
    expect(truncate("абвг", 0)).toBe("…");
  });
});

describe("joinNames", () => {
  it("на пустом списке возвращает пустую строку", () => {
    expect(joinNames([])).toBe("");
  });

  it("одно имя отдаёт как есть", () => {
    expect(joinNames(["Оля"])).toBe("Оля");
  });

  it("два имени соединяет союзом «и»", () => {
    expect(joinNames(["Оля", "Саша"])).toBe("Оля и Саша");
  });

  it("третье имя сворачивает в «и ещё 1»", () => {
    expect(joinNames(["Оля", "Саша", "Костя"])).toBe("Оля, Саша и ещё 1");
    expect(joinNames(["Оля", "Саша", "Костя"], 2)).toBe("Оля, Саша и ещё 1");
  });

  it("четыре имени сворачивает в «и ещё 2»", () => {
    expect(joinNames(["Оля", "Саша", "Костя", "Жора"], 2)).toBe("Оля, Саша и ещё 2");
  });

  it("пять имён при пороге по умолчанию — «и ещё 3»", () => {
    expect(joinNames(["Оля", "Саша", "Костя", "Максим", "Жора"])).toBe("Оля, Саша и ещё 3");
  });

  it("уважает более широкий порог", () => {
    expect(joinNames(["Оля", "Саша", "Костя"], 3)).toBe("Оля, Саша и Костя");
    expect(joinNames(["Оля", "Саша", "Костя", "Максим"], 3)).toBe("Оля, Саша, Костя и ещё 1");
  });
});
