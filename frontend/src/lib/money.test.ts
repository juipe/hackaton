import { describe, expect, it } from "vitest";

import {
  DEFAULT_CURRENCY,
  balanceToneClass,
  centsToInput,
  currencySymbol,
  distributeByWeight,
  formatAmount,
  formatCompact,
  formatMoney,
  formatMoneyRounded,
  formatSigned,
  parseAmountToCents,
  splitEqually,
} from "@/lib/money";

/**
 * Все суммы пишутся по-русски: разряды разделяет неразрывный пробел U+00A0,
 * копейки отделяются запятой, знак «₽» стоит после числа — тоже за неразрывным
 * пробелом. В ожиданиях он записан экранированным: в коде его иначе не видно.
 */
const NBSP = "\u00A0";

describe("DEFAULT_CURRENCY", () => {
  it("единственная валюта в системе — рубль", () => {
    expect(DEFAULT_CURRENCY).toBe("RUB");
  });
});

describe("currencySymbol", () => {
  it("всегда возвращает рубль", () => {
    expect(currencySymbol("RUB")).toBe("₽");
    expect(currencySymbol("rub")).toBe("₽");
  });

  it("возвращает рубль и без аргумента, и для любого чужого кода", () => {
    expect(currencySymbol()).toBe("₽");
    expect(currencySymbol("EUR")).toBe("₽");
    expect(currencySymbol("USD")).toBe("₽");
    expect(currencySymbol("")).toBe("₽");
  });
});

describe("formatMoney", () => {
  it("покрывает таблицу контракта", () => {
    expect(formatMoney(0)).toBe(`0,00${NBSP}₽`);
    expect(formatMoney(1234)).toBe(`12,34${NBSP}₽`);
    expect(formatMoney(123_456)).toBe(`1${NBSP}234,56${NBSP}₽`);
    expect(formatMoney(600_000_000)).toBe(`6${NBSP}000${NBSP}000,00${NBSP}₽`);
    expect(formatMoney(-123_456)).toBe(`-1${NBSP}234,56${NBSP}₽`);
  });

  it("ставит минус перед числом, а знак валюты — после", () => {
    expect(formatMoney(-1234)).toBe(`-12,34${NBSP}₽`);
  });

  it("дополняет копейки нулями", () => {
    expect(formatMoney(5)).toBe(`0,05${NBSP}₽`);
    expect(formatMoney(50)).toBe(`0,50${NBSP}₽`);
    expect(formatMoney(100)).toBe(`1,00${NBSP}₽`);
  });

  it("группирует разряды неразрывными пробелами", () => {
    expect(formatMoney(123_456_789)).toBe(`1${NBSP}234${NBSP}567,89${NBSP}₽`);
    expect(formatMoney(-123_456_789)).toBe(`-1${NBSP}234${NBSP}567,89${NBSP}₽`);
  });

  it("не содержит обычных пробелов — сумма не должна переноситься", () => {
    for (const cents of [0, 1234, 123_456, 600_000_000, -123_456_789]) {
      expect(formatMoney(cents)).not.toContain(" ");
    }
  });

  it("игнорирует переданный код валюты — рубль в любом случае", () => {
    expect(formatMoney(1234, "RUB")).toBe(`12,34${NBSP}₽`);
    expect(formatMoney(1234, "USD")).toBe(`12,34${NBSP}₽`);
  });

  it("никогда не печатает NaN", () => {
    expect(formatMoney(Number.NaN)).toBe(`0,00${NBSP}₽`);
    expect(formatMoney(Number.POSITIVE_INFINITY)).toBe(`0,00${NBSP}₽`);
  });
});

describe("formatSigned", () => {
  it("покрывает таблицу контракта", () => {
    expect(formatSigned(123_456)).toBe(`+1${NBSP}234,56${NBSP}₽`);
    expect(formatSigned(-123_456)).toBe(`-1${NBSP}234,56${NBSP}₽`);
    expect(formatSigned(0)).toBe(`0,00${NBSP}₽`);
  });

  it("помечает плюсом только то, что вам должны", () => {
    expect(formatSigned(8000)).toBe(`+80,00${NBSP}₽`);
    expect(formatSigned(-4000)).toBe(`-40,00${NBSP}₽`);
    expect(formatSigned(150)).toBe(`+1,50${NBSP}₽`);
  });
});

describe("formatAmount", () => {
  it("убирает знак валюты и разряды — это значение для поля ввода", () => {
    expect(formatAmount(123_456)).toBe("1234,56");
    expect(formatAmount(-5)).toBe("-0,05");
    expect(formatAmount(0)).toBe("0,00");
    expect(formatAmount(600_000_000)).toBe("6000000,00");
  });

  it("не содержит ни пробелов, ни рубля", () => {
    const text = formatAmount(123_456_789);
    expect(text).toBe("1234567,89");
    expect(text).not.toContain(NBSP);
    expect(text).not.toContain("₽");
  });
});

describe("formatMoneyRounded", () => {
  it("отбрасывает копейки и группирует разряды", () => {
    expect(formatMoneyRounded(3_973_000)).toBe(`39${NBSP}730${NBSP}₽`);
    expect(formatMoneyRounded(54_000)).toBe(`540${NBSP}₽`);
    expect(formatMoneyRounded(600_000_000)).toBe(`6${NBSP}000${NBSP}000${NBSP}₽`);
  });

  it("округляет к ближайшему рублю", () => {
    expect(formatMoneyRounded(12_349)).toBe(`123${NBSP}₽`);
    expect(formatMoneyRounded(12_350)).toBe(`124${NBSP}₽`);
    expect(formatMoneyRounded(-12_350)).toBe(`−124${NBSP}₽`);
  });

  it("при signed ставит плюс только положительным", () => {
    expect(formatMoneyRounded(3_973_000, { signed: true })).toBe(`+39${NBSP}730${NBSP}₽`);
    expect(formatMoneyRounded(-3_973_000, { signed: true })).toBe(`−39${NBSP}730${NBSP}₽`);
    expect(formatMoneyRounded(0, { signed: true })).toBe(`0${NBSP}₽`);
  });

  it("минус — типографский U+2212, а не дефис", () => {
    const text = formatMoneyRounded(-100_000);
    expect(text.startsWith("−")).toBe(true);
    expect(text).not.toContain("-");
  });

  it("округлённый в ноль остаток не получает знака", () => {
    expect(formatMoneyRounded(-49)).toBe(`0${NBSP}₽`);
    expect(formatMoneyRounded(49, { signed: true })).toBe(`0${NBSP}₽`);
    expect(formatMoneyRounded(0)).toBe(`0${NBSP}₽`);
  });

  it("некорректное число читается как ноль", () => {
    expect(formatMoneyRounded(Number.NaN)).toBe(`0${NBSP}₽`);
  });
});

describe("formatCompact", () => {
  it("покрывает таблицу контракта", () => {
    expect(formatCompact(54_000)).toBe(`540${NBSP}₽`);
    expect(formatCompact(123_456)).toBe(`1,2${NBSP}тыс${NBSP}₽`);
    expect(formatCompact(600_000_000)).toBe(`6${NBSP}млн${NBSP}₽`);
  });

  it("до тысячи рублей показывает целые рубли", () => {
    expect(formatCompact(0)).toBe(`0${NBSP}₽`);
    expect(formatCompact(4250)).toBe(`42${NBSP}₽`);
    expect(formatCompact(99_999)).toBe(`999${NBSP}₽`);
  });

  it("переходит на «тыс» ровно с тысячи рублей", () => {
    expect(formatCompact(100_000)).toBe(`1${NBSP}тыс${NBSP}₽`);
    expect(formatCompact(150_000)).toBe(`1,5${NBSP}тыс${NBSP}₽`);
    expect(formatCompact(99_950_000)).toBe(`999,5${NBSP}тыс${NBSP}₽`);
  });

  it("переходит на «млн» ровно с миллиона рублей", () => {
    expect(formatCompact(100_000_000)).toBe(`1${NBSP}млн${NBSP}₽`);
    expect(formatCompact(250_000_000)).toBe(`2,5${NBSP}млн${NBSP}₽`);
  });

  it("округляет к порогу, а не показывает «1000 тыс»", () => {
    expect(formatCompact(99_999_900)).toBe(`1${NBSP}млн${NBSP}₽`);
    expect(formatCompact(99_995_000)).toBe(`1${NBSP}млн${NBSP}₽`);
    expect(formatCompact(99_994_900)).toBe(`999,9${NBSP}тыс${NBSP}₽`);
  });

  it("опускает нулевую дробную часть", () => {
    expect(formatCompact(600_000)).toBe(`6${NBSP}тыс${NBSP}₽`);
    expect(formatCompact(600_000_000)).not.toContain(",");
  });

  it("держит минус впереди", () => {
    expect(formatCompact(-100_000)).toBe(`-1${NBSP}тыс${NBSP}₽`);
    expect(formatCompact(-100_000_000)).toBe(`-1${NBSP}млн${NBSP}₽`);
  });

  it("не содержит обычных пробелов", () => {
    for (const cents of [0, 54_000, 123_456, 600_000_000]) {
      expect(formatCompact(cents)).not.toContain(" ");
    }
  });
});

describe("parseAmountToCents", () => {
  it("читает копейки после запятой", () => {
    expect(parseAmountToCents("12,34")).toBe(1234);
    expect(parseAmountToCents(",5")).toBe(50);
  });

  it("читает точку как десятичный разделитель тоже", () => {
    expect(parseAmountToCents("12.34")).toBe(1234);
    expect(parseAmountToCents(".5")).toBe(50);
  });

  it("читает целое число", () => {
    expect(parseAmountToCents("12")).toBe(1200);
  });

  it("дополняет одну цифру после запятой", () => {
    expect(parseAmountToCents("12,3")).toBe(1230);
  });

  it("округляет третий знак в большую сторону от половины", () => {
    expect(parseAmountToCents("12,345")).toBe(1235);
    expect(parseAmountToCents("12,344")).toBe(1234);
    expect(parseAmountToCents("0,005")).toBe(1);
    expect(parseAmountToCents("0,004")).toBe(0);
  });

  it("переваривает обычные и неразрывные пробелы между разрядами", () => {
    expect(parseAmountToCents("  12,34  ")).toBe(1234);
    expect(parseAmountToCents("1 234,50")).toBe(123_450);
    expect(parseAmountToCents(`1${NBSP}234,50`)).toBe(123_450);
    expect(parseAmountToCents(`6${NBSP}000${NBSP}000,00`)).toBe(600_000_000);
  });

  it("переваривает знак рубля внутри строки", () => {
    expect(parseAmountToCents("1234,56 ₽")).toBe(123_456);
    expect(parseAmountToCents(`1${NBSP}234,56${NBSP}₽`)).toBe(123_456);
    expect(parseAmountToCents("₽1234,56")).toBe(123_456);
  });

  it("читает обратно то, что напечатал formatMoney", () => {
    for (const cents of [0, 5, 1234, 123_456, 600_000_000, -123_456]) {
      expect(parseAmountToCents(formatMoney(cents))).toBe(cents);
    }
  });

  it("читает отрицательные суммы", () => {
    expect(parseAmountToCents("-12,34")).toBe(-1234);
    expect(parseAmountToCents("-0,05")).toBe(-5);
  });

  it("возвращает null на пустой строке", () => {
    expect(parseAmountToCents("")).toBeNull();
    expect(parseAmountToCents("   ")).toBeNull();
    expect(parseAmountToCents("₽")).toBeNull();
  });

  it("возвращает null на мусоре", () => {
    expect(parseAmountToCents("abc")).toBeNull();
    expect(parseAmountToCents("12,34,56")).toBeNull();
    expect(parseAmountToCents("12.34.56")).toBeNull();
    expect(parseAmountToCents("€12")).toBeNull();
    expect(parseAmountToCents("12e3")).toBeNull();
    expect(parseAmountToCents(",")).toBeNull();
    expect(parseAmountToCents("-")).toBeNull();
  });

  it("остаётся целочисленной: результат всегда целое число копеек", () => {
    for (const text of ["0,01", "12,345", "1 234,56", "999999,99"]) {
      const cents = parseAmountToCents(text);
      expect(cents).not.toBeNull();
      expect(Number.isInteger(cents as number)).toBe(true);
    }
  });
});

describe("centsToInput", () => {
  it("печатает строку для поля ввода", () => {
    expect(centsToInput(1234)).toBe("12,34");
    expect(centsToInput(0)).toBe("0,00");
    expect(centsToInput(-1234)).toBe("-12,34");
  });

  it("печатает пустую строку, если суммы нет", () => {
    expect(centsToInput(null)).toBe("");
    expect(centsToInput(undefined)).toBe("");
    expect(centsToInput(Number.NaN)).toBe("");
  });

  it("делает полный круг через parseAmountToCents", () => {
    for (const cents of [0, 1, 5, 99, 100, 1234, 100_000, 123_456_789, 600_000_000, -1234, -5]) {
      expect(parseAmountToCents(centsToInput(cents))).toBe(cents);
      expect(parseAmountToCents(formatAmount(cents))).toBe(cents);
    }
  });
});

describe("balanceToneClass", () => {
  it("отдаёт знак баланса отдельным токенам, а не бренду", () => {
    expect(balanceToneClass(1)).toBe("text-positive");
    expect(balanceToneClass(-1)).toBe("text-negative");
    expect(balanceToneClass(0)).toBe("text-muted-foreground");
  });

  it("не использует утилиты палитры Tailwind", () => {
    for (const cents of [1, -1, 0]) {
      expect(balanceToneClass(cents)).not.toContain("emerald");
      expect(balanceToneClass(cents)).not.toContain("rose");
    }
  });
});

describe("splitEqually", () => {
  it("делит нацело, когда может", () => {
    expect(splitEqually(9000, 3)).toEqual([3000, 3000, 3000]);
  });

  it("раздаёт остаток с начала, по одной копейке", () => {
    expect(splitEqually(1000, 3)).toEqual([334, 333, 333]);
    expect(splitEqually(10, 4)).toEqual([3, 3, 2, 2]);
    expect(splitEqually(1, 3)).toEqual([1, 0, 0]);
  });

  it("справляется с одним участником и нулевой суммой", () => {
    expect(splitEqually(1234, 1)).toEqual([1234]);
    expect(splitEqually(0, 3)).toEqual([0, 0, 0]);
  });

  it("возвращает пусто, когда делить не между кем", () => {
    expect(splitEqually(1000, 0)).toEqual([]);
    expect(splitEqually(1000, -2)).toEqual([]);
  });

  it("никогда не разводит участников больше чем на копейку", () => {
    const shares = splitEqually(10_001, 7);
    expect(Math.max(...shares) - Math.min(...shares)).toBe(1);
  });
});

describe("distributeByWeight", () => {
  it("делит по процентам", () => {
    expect(distributeByWeight(10_000, [50, 30, 20])).toEqual([5000, 3000, 2000]);
  });

  it("делит по долям", () => {
    expect(distributeByWeight(1000, [2, 1, 1])).toEqual([500, 250, 250]);
  });

  it("отдаёт остаток наибольшим хвостам, при равенстве — по порядку", () => {
    expect(distributeByWeight(100, [1, 1, 1])).toEqual([34, 33, 33]);
    expect(distributeByWeight(101, [1, 2])).toEqual([34, 67]);
  });

  it("нулевой вес не получает ничего, но сумма всё равно сходится", () => {
    expect(distributeByWeight(999, [0, 1, 1])).toEqual([0, 500, 499]);
    expect(distributeByWeight(1000, [0, 3, 1])).toEqual([0, 750, 250]);
  });

  it("возвращает нули, когда все веса нулевые", () => {
    expect(distributeByWeight(1000, [0, 0, 0])).toEqual([0, 0, 0]);
  });

  it("справляется с процентами, которые не делятся нацело", () => {
    const result = distributeByWeight(100, [33.333333, 33.333333, 33.333333]);
    expect(result.reduce((sum, value) => sum + value, 0)).toBe(100);
    expect(result).toEqual([34, 33, 33]);
  });

  it("возвращает пусто, когда весов нет", () => {
    expect(distributeByWeight(1000, [])).toEqual([]);
  });
});

describe("инварианты деления", () => {
  const amounts = [1, 2, 3, 7, 33, 99, 100, 101, 999, 1000, 1234, 9999, 100_000, 123_457];
  const counts = [1, 2, 3, 4, 5, 6, 7, 8, 9, 12, 17];

  it("splitEqually всегда даёт в сумме ровно исходную сумму", () => {
    for (const amount of amounts) {
      for (const count of counts) {
        const shares = splitEqually(amount, count);
        expect(shares).toHaveLength(count);
        expect(shares.reduce((sum, value) => sum + value, 0)).toBe(amount);
        expect(Math.max(...shares) - Math.min(...shares)).toBeLessThanOrEqual(1);
        expect(shares.every((value) => Number.isInteger(value))).toBe(true);
      }
    }
  });

  it("distributeByWeight всегда даёт в сумме ровно исходную сумму", () => {
    for (const amount of amounts) {
      for (const count of counts) {
        const ascending = Array.from({ length: count }, (_, index) => index + 1);
        const lumpy = ascending.map((weight) => weight * 7 + 0.5);
        // Нулевой вес имеет смысл, только когда кто-то ещё несёт ненулевой:
        // из полностью нулевых весов распределять нечего.
        const withZero =
          count > 1 ? ascending.map((weight, index) => (index === 0 ? 0 : weight)) : ascending;

        for (const weights of [ascending, withZero, lumpy]) {
          const result = distributeByWeight(amount, weights);
          expect(result).toHaveLength(count);
          expect(result.reduce((sum, value) => sum + value, 0)).toBe(amount);
          expect(result.every((value) => Number.isInteger(value))).toBe(true);
        }
      }
    }
  });
});
