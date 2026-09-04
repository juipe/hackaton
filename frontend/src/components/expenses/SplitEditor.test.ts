/**
 * The split preview is the one piece of arithmetic the user watches while they
 * type, and it has to agree with the server's split engine cent for cent — a
 * preview that promises a split the API rejects is worse than no preview.
 *
 * These cases cover the arithmetic only; SplitEditor.render.test.tsx covers what
 * the same maths looks like on screen.
 */

import { describe, expect, it } from "vitest";

// Imported through SplitEditor, which the component contract requires to
// re-export it — so this also pins that export in place.
import { computeSplitPreview } from "@/components/expenses/SplitEditor";
import {
  buildParticipantValues,
  formatPercentInput,
  seedSplitRows,
} from "@/components/expenses/splitMath";
import type { SplitMode } from "@/types/api";

const A = "user-1";
const B = "user-2";
const C = "user-3";
const THREE = [A, B, C];

function preview(
  mode: SplitMode,
  amountCents: number,
  rows: Record<string, string>,
  participantIds: string[] = THREE,
) {
  return computeSplitPreview({ mode, amountCents, participantIds, rows });
}

function total(amounts: Record<string, number>): number {
  return Object.values(amounts).reduce((sum, value) => sum + value, 0);
}

describe("computeSplitPreview — guards", () => {
  it("rejects an expense with nobody in it", () => {
    const result = preview("equal", 1000, {}, []);
    expect(result.error).toBe("Добавьте хотя бы одного участника");
    expect(result.amounts).toEqual({});
    expect(result.assignedCents).toBe(0);
  });

  it("rejects a zero or negative amount", () => {
    expect(preview("equal", 0, {}).error).toBe("Сумма должна быть больше нуля");
    expect(preview("equal", -500, {}).error).toBe("Сумма должна быть больше нуля");
  });

  it("rejects an unusable amount instead of producing NaN shares", () => {
    const result = preview("equal", Number.NaN, {});
    expect(result.error).toBe("Сумма должна быть больше нуля");
    expect(Object.values(result.amounts).every(Number.isFinite)).toBe(true);
  });
});

describe("computeSplitPreview — equal", () => {
  it("divides evenly and ignores whatever is in the rows", () => {
    const result = preview("equal", 9000, { [A]: "999", [B]: "nonsense", [C]: "" });
    expect(result.amounts).toEqual({ [A]: 3000, [B]: 3000, [C]: 3000 });
    expect(result.error).toBeNull();
    expect(result.assignedCents).toBe(9000);
  });

  it("hands the leftover cents out from the front, like the server does", () => {
    const result = preview("equal", 1000, {});
    expect(result.amounts).toEqual({ [A]: 334, [B]: 333, [C]: 333 });
    expect(total(result.amounts)).toBe(1000);
  });

  it("gives a single participant the whole amount", () => {
    const result = preview("equal", 1234, {}, [A]);
    expect(result.amounts).toEqual({ [A]: 1234 });
    expect(result.error).toBeNull();
  });
});

describe("computeSplitPreview — exact", () => {
  it("accepts amounts that add up to the total", () => {
    const result = preview("exact", 12_000, { [A]: "40.00", [B]: "50", [C]: "30" });
    expect(result.amounts).toEqual({ [A]: 4000, [B]: 5000, [C]: 3000 });
    expect(result.error).toBeNull();
    expect(result.assignedCents).toBe(12_000);
  });

  it("names the mismatch with the server's wording", () => {
    const result = preview("exact", 12_000, { [A]: "40", [B]: "50", [C]: "20" });
    expect(result.error).toBe("Сумма частей должна совпадать с общей суммой");
    expect(result.assignedCents).toBe(11_000);
  });

  it("still shows what was typed while the total is wrong", () => {
    const result = preview("exact", 12_000, { [A]: "40", [B]: "", [C]: "" });
    expect(result.amounts).toEqual({ [A]: 4000, [B]: 0, [C]: 0 });
    expect(result.assignedCents).toBe(4000);
    expect(result.error).toBe("Сумма частей должна совпадать с общей суммой");
  });

  it("rejects a negative amount before complaining about the total", () => {
    const result = preview("exact", 12_000, { [A]: "-10", [B]: "130", [C]: "0" });
    expect(result.error).toBe("Суммы не могут быть отрицательными");
  });

  it("reads a comma as the decimal separator, the way a Russian keyboard types it", () => {
    const result = preview("exact", 12_000, { [A]: "40,00", [B]: "50,50", [C]: "29,50" });
    expect(result.amounts).toEqual({ [A]: 4000, [B]: 5050, [C]: 2950 });
    expect(result.error).toBeNull();
  });

  it("is not fooled by a one-cent shortfall", () => {
    const result = preview("exact", 10_000, { [A]: "33.33", [B]: "33.33", [C]: "33.33" });
    expect(result.assignedCents).toBe(9999);
    expect(result.error).toBe("Сумма частей должна совпадать с общей суммой");
  });
});

describe("computeSplitPreview — percentage", () => {
  it("splits when the percentages total exactly 100", () => {
    const result = preview("percentage", 10_000, { [A]: "50", [B]: "30", [C]: "20" });
    expect(result.amounts).toEqual({ [A]: 5000, [B]: 3000, [C]: 2000 });
    expect(result.error).toBeNull();
    expect(result.assignedCents).toBe(10_000);
  });

  it("accepts six-decimal thirds, and still sums to the exact total", () => {
    const result = preview("percentage", 10_000, {
      [A]: "33.333334",
      [B]: "33.333333",
      [C]: "33.333333",
    });
    expect(result.error).toBeNull();
    expect(total(result.amounts)).toBe(10_000);
  });

  it("complains when the percentages do not total 100", () => {
    const result = preview("percentage", 10_000, { [A]: "50", [B]: "30", [C]: "10" });
    expect(result.error).toBe("Сумма процентов должна быть 100%");
    // The rows still show their worth, so the user can spot the wrong one.
    expect(result.amounts).toEqual({ [A]: 5000, [B]: 3000, [C]: 1000 });
    expect(result.assignedCents).toBe(9000);
  });

  it("complains when the percentages overshoot 100", () => {
    const result = preview("percentage", 10_000, { [A]: "50", [B]: "30", [C]: "40" });
    expect(result.error).toBe("Сумма процентов должна быть 100%");
    expect(result.assignedCents).toBe(12_000);
  });

  it("treats a blank row as zero rather than as a silent 100", () => {
    const result = preview("percentage", 10_000, { [A]: "100", [B]: "", [C]: "" });
    expect(result.error).toBeNull();
    expect(result.amounts).toEqual({ [A]: 10_000, [B]: 0, [C]: 0 });
  });

  it("rejects a negative percentage", () => {
    const result = preview("percentage", 10_000, { [A]: "120", [B]: "-20", [C]: "0" });
    expect(result.error).toBe("Проценты не могут быть отрицательными");
  });
});

describe("computeSplitPreview — shares", () => {
  it("weights the split by share count", () => {
    const result = preview("shares", 1000, { [A]: "2", [B]: "1", [C]: "1" });
    expect(result.amounts).toEqual({ [A]: 500, [B]: 250, [C]: 250 });
    expect(result.error).toBeNull();
    expect(result.assignedCents).toBe(1000);
  });

  it("gives a zero share nothing while the rest still sums exactly", () => {
    const result = preview("shares", 999, { [A]: "0", [B]: "1", [C]: "1" });
    expect(result.amounts).toEqual({ [A]: 0, [B]: 500, [C]: 499 });
    expect(total(result.amounts)).toBe(999);
    expect(result.error).toBeNull();
  });

  it("rejects an all-zero total instead of dividing by zero", () => {
    const result = preview("shares", 1000, { [A]: "0", [B]: "0", [C]: "0" });
    expect(result.error).toBe("Сумма долей должна быть больше нуля");
    expect(result.amounts).toEqual({ [A]: 0, [B]: 0, [C]: 0 });
  });

  it("treats every blank row as an all-zero total", () => {
    const result = preview("shares", 1000, {});
    expect(result.error).toBe("Сумма долей должна быть больше нуля");
  });

  it("rejects fractional shares", () => {
    const result = preview("shares", 1000, { [A]: "1.5", [B]: "1", [C]: "1" });
    expect(result.error).toBe("Доли должны быть целыми числами");
  });

  it("rejects negative shares", () => {
    const result = preview("shares", 1000, { [A]: "-1", [B]: "2", [C]: "1" });
    expect(result.error).toBe("Доли не могут быть отрицательными");
  });
});

describe("computeSplitPreview — the invariant that matters", () => {
  const cases: { mode: SplitMode; rows: Record<string, string> }[] = [
    { mode: "equal", rows: {} },
    { mode: "percentage", rows: { [A]: "50", [B]: "30", [C]: "20" } },
    { mode: "percentage", rows: { [A]: "33.333334", [B]: "33.333333", [C]: "33.333333" } },
    { mode: "shares", rows: { [A]: "1", [B]: "1", [C]: "1" } },
    { mode: "shares", rows: { [A]: "3", [B]: "1", [C]: "0" } },
    { mode: "shares", rows: { [A]: "7", [B]: "5", [C]: "2" } },
  ];

  it("always assigns exactly the expense amount whenever there is no error", () => {
    for (let amountCents = 1; amountCents <= 1000; amountCents += 7) {
      for (const { mode, rows } of cases) {
        const result = computeSplitPreview({
          mode,
          amountCents,
          participantIds: THREE,
          rows,
        });
        if (result.error !== null) continue;
        expect(total(result.amounts)).toBe(amountCents);
        expect(result.assignedCents).toBe(amountCents);
        expect(Object.values(result.amounts).every(Number.isInteger)).toBe(true);
      }
    }
  });

  it("holds for an exact split too, at every amount", () => {
    for (let amountCents = 1; amountCents <= 500; amountCents += 3) {
      const rows = { [A]: "0.01", [B]: "0.01", [C]: ((amountCents - 2) / 100).toFixed(2) };
      const result = preview("exact", amountCents, rows);
      if (result.error !== null) continue;
      expect(total(result.amounts)).toBe(amountCents);
    }
  });
});

describe("formatPercentInput", () => {
  it("strips trailing zeros but keeps real precision", () => {
    expect(formatPercentInput(25_000_000)).toBe("25");
    expect(formatPercentInput(33_333_334)).toBe("33.333334");
    expect(formatPercentInput(50_500_000)).toBe("50.5");
    expect(formatPercentInput(0)).toBe("0");
  });
});

describe("seedSplitRows", () => {
  it("leaves equal mode with no rows to fill in", () => {
    expect(seedSplitRows("equal", THREE, 10_000)).toEqual({});
  });

  it("seeds exact mode with an even split that already validates", () => {
    const rows = seedSplitRows("exact", THREE, 1000);
    // Rouble typography: the seeded inputs carry a comma, and the preview parses
    // them straight back without complaining.
    expect(rows).toEqual({ [A]: "3,34", [B]: "3,33", [C]: "3,33" });
    expect(computeSplitPreview({ mode: "exact", amountCents: 1000, participantIds: THREE, rows }).error).toBeNull();
  });

  it("seeds percentages that total exactly 100, not three rounded thirds", () => {
    const rows = seedSplitRows("percentage", THREE, 10_000);
    // Rouble typography again: the visible field shows a comma, the payload a dot.
    expect(rows).toEqual({ [A]: "33,333334", [B]: "33,333333", [C]: "33,333333" });
    expect(
      computeSplitPreview({ mode: "percentage", amountCents: 10_000, participantIds: THREE, rows })
        .error,
    ).toBeNull();
  });

  it("seeds one share each", () => {
    expect(seedSplitRows("shares", THREE, 10_000)).toEqual({ [A]: "1", [B]: "1", [C]: "1" });
  });

  it("leaves exact rows blank when there is no amount to split yet", () => {
    expect(seedSplitRows("exact", THREE, 0)).toEqual({ [A]: "", [B]: "", [C]: "" });
  });
});

describe("buildParticipantValues", () => {
  it("sends null for equal, cents for exact, and the raw weight otherwise", () => {
    const amounts = { [A]: 5000, [B]: 3000, [C]: 2000 };

    expect(
      buildParticipantValues({ mode: "equal", participantIds: THREE, rows: {}, amounts }),
    ).toEqual([
      { user_id: A, value: null },
      { user_id: B, value: null },
      { user_id: C, value: null },
    ]);

    expect(
      buildParticipantValues({
        mode: "exact",
        participantIds: THREE,
        rows: { [A]: "50", [B]: "30", [C]: "20" },
        amounts,
      }),
    ).toEqual([
      { user_id: A, value: "5000" },
      { user_id: B, value: "3000" },
      { user_id: C, value: "2000" },
    ]);

    expect(
      buildParticipantValues({
        mode: "percentage",
        participantIds: THREE,
        rows: { [A]: "33.333334", [B]: "33.333333", [C]: "33.333333" },
        amounts,
      }),
    ).toEqual([
      { user_id: A, value: "33.333334" },
      { user_id: B, value: "33.333333" },
      { user_id: C, value: "33.333333" },
    ]);

    expect(
      buildParticipantValues({
        mode: "shares",
        participantIds: THREE,
        rows: { [A]: "2", [B]: "1", [C]: "" },
        amounts,
      }),
    ).toEqual([
      { user_id: A, value: "2" },
      { user_id: B, value: "1" },
      { user_id: C, value: "0" },
    ]);
  });
});
