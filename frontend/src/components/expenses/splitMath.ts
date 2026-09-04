/**
 * Pure split arithmetic behind the expense form.
 *
 * Every rule here mirrors `app/services/split_engine.py`: the same
 * largest-remainder distribution, the same validation order and the same wording,
 * so the live preview can never promise a split the server would reject.
 */

import { centsToInput, distributeByWeight, parseAmountToCents, splitEqually } from "@/lib/money";
import type { ParticipantInput, SplitMode } from "@/types/api";

/**
 * Percentages are `Numeric(12, 6)` server-side, so six decimals is the full
 * precision the API round-trips. Holding them as integer micro-percent keeps the
 * "must total exactly 100%" test free of floating-point drift.
 */
const PERCENT_DECIMALS = 6;
const PERCENT_SCALE = 10 ** PERCENT_DECIMALS;
const FULL_PERCENT = 100 * PERCENT_SCALE;

/**
 * Shares are whole numbers, but they are parsed with three decimals so that
 * `1.5` can be reported as "not a whole number" instead of silently truncated.
 */
const SHARE_DECIMALS = 3;
const SHARE_SCALE = 10 ** SHARE_DECIMALS;

export interface SplitPreview {
  /** Per-user cents. Sums to `amountCents` whenever `error` is null. */
  amounts: Record<string, number>;
  error: string | null;
  assignedCents: number;
}

function clean(text: string | undefined): string {
  return (text ?? "").trim().replace(/\s/g, "").replace(",", ".");
}

/** `"33.5", 6` → `33500000`. Returns null for blank or unusable input. */
function parseScaled(text: string | undefined, decimals: number): number | null {
  const cleaned = clean(text);
  if (!cleaned) return null;
  if (!/^-?\d*\.?\d*$/.test(cleaned)) return null;
  const negative = cleaned.startsWith("-");
  const [whole = "", fraction = ""] = cleaned.replace("-", "").split(".");
  if (!whole && !fraction) return null;
  const scale = 10 ** decimals;
  const padded = fraction.slice(0, decimals).padEnd(decimals, "0");
  const minor = decimals > 0 ? Number.parseInt(padded, 10) : 0;
  const value = (whole ? Number.parseInt(whole, 10) : 0) * scale + minor;
  if (!Number.isFinite(value)) return null;
  return negative ? -value : value;
}

/** `33333334` → `"33.333334"`, `25000000` → `"25"`. */
export function formatPercentInput(micro: number): string {
  const rounded = Math.round(micro);
  const sign = rounded < 0 ? "-" : "";
  const abs = Math.abs(rounded);
  const whole = Math.trunc(abs / PERCENT_SCALE);
  const fraction = String(abs % PERCENT_SCALE)
    .padStart(PERCENT_DECIMALS, "0")
    .replace(/0+$/, "");
  return `${sign}${whole}${fraction ? `.${fraction}` : ""}`;
}

export function sumPercentMicro(
  participantIds: string[],
  rows: Record<string, string>,
): number {
  return participantIds.reduce(
    (sum, id) => sum + (parseScaled(rows[id], PERCENT_DECIMALS) ?? 0),
    0,
  );
}

export function readShareCount(text: string | undefined): number {
  return Math.round((parseScaled(text, SHARE_DECIMALS) ?? 0) / SHARE_SCALE);
}

export function sumShareCount(
  participantIds: string[],
  rows: Record<string, string>,
): number {
  const milli = participantIds.reduce(
    (sum, id) => sum + (parseScaled(rows[id], SHARE_DECIMALS) ?? 0),
    0,
  );
  return Math.round((milli / SHARE_SCALE) * 1000) / 1000;
}

/**
 * The live preview. Pure, so the form, the editor and the tests all agree.
 *
 * A blank field counts as zero rather than as a separate "you missed someone"
 * error: while the user is still typing, "осталось распределить 40,00 ₽" is far
 * more useful than a scolding, and the totals check catches it either way.
 */
export function computeSplitPreview(args: {
  mode: SplitMode;
  amountCents: number;
  participantIds: string[];
  rows: Record<string, string>;
}): SplitPreview {
  const { mode, amountCents, participantIds, rows } = args;
  const amounts: Record<string, number> = {};
  for (const id of participantIds) amounts[id] = 0;

  if (participantIds.length === 0) {
    return {
      amounts,
      error: "Добавьте хотя бы одного участника",
      assignedCents: 0,
    };
  }
  if (!Number.isFinite(amountCents) || amountCents <= 0) {
    return { amounts, error: "Сумма должна быть больше нуля", assignedCents: 0 };
  }

  if (mode === "equal") {
    const parts = splitEqually(amountCents, participantIds.length);
    participantIds.forEach((id, index) => {
      amounts[id] = parts[index];
    });
    return { amounts, error: null, assignedCents: amountCents };
  }

  if (mode === "exact") {
    // The row holds a major-unit amount typed by a human; the API wants cents.
    const values = participantIds.map((id) => parseAmountToCents(rows[id] ?? "") ?? 0);
    participantIds.forEach((id, index) => {
      amounts[id] = values[index];
    });
    const assignedCents = values.reduce((sum, value) => sum + value, 0);
    if (values.some((value) => value < 0)) {
      return { amounts, error: "Суммы не могут быть отрицательными", assignedCents };
    }
    if (assignedCents !== amountCents) {
      return {
        amounts,
        error: "Сумма частей должна совпадать с общей суммой",
        assignedCents,
      };
    }
    return { amounts, error: null, assignedCents };
  }

  if (mode === "percentage") {
    const values = participantIds.map(
      (id) => parseScaled(rows[id], PERCENT_DECIMALS) ?? 0,
    );
    if (values.some((value) => value < 0)) {
      return { amounts, error: "Проценты не могут быть отрицательными", assignedCents: 0 };
    }
    const total = values.reduce((sum, value) => sum + value, 0);
    if (total !== FULL_PERCENT) {
      // Show what each percentage is worth anyway — seeing "50% → 60,00 ₽" is how
      // the user works out which row is wrong.
      participantIds.forEach((id, index) => {
        amounts[id] = Math.round((amountCents * values[index]) / FULL_PERCENT);
      });
      const assignedCents = participantIds.reduce((sum, id) => sum + amounts[id], 0);
      return { amounts, error: "Сумма процентов должна быть 100%", assignedCents };
    }
    const parts = distributeByWeight(amountCents, values);
    participantIds.forEach((id, index) => {
      amounts[id] = parts[index];
    });
    return { amounts, error: null, assignedCents: amountCents };
  }

  const values = participantIds.map((id) => parseScaled(rows[id], SHARE_DECIMALS) ?? 0);
  if (values.some((value) => value < 0)) {
    return { amounts, error: "Доли не могут быть отрицательными", assignedCents: 0 };
  }
  if (values.some((value) => value % SHARE_SCALE !== 0)) {
    return { amounts, error: "Доли должны быть целыми числами", assignedCents: 0 };
  }
  const total = values.reduce((sum, value) => sum + value, 0);
  if (total === 0) {
    return { amounts, error: "Сумма долей должна быть больше нуля", assignedCents: 0 };
  }
  const parts = distributeByWeight(amountCents, values);
  participantIds.forEach((id, index) => {
    amounts[id] = parts[index];
  });
  return { amounts, error: null, assignedCents: amountCents };
}

/**
 * Fresh inputs for a mode the user just switched to, chosen so the form is never
 * left in a state the server would reject.
 */
export function seedSplitRows(
  mode: SplitMode,
  participantIds: string[],
  amountCents: number,
): Record<string, string> {
  const rows: Record<string, string> = {};
  if (mode === "equal" || participantIds.length === 0) return rows;

  if (mode === "exact") {
    const usable = Number.isFinite(amountCents) && amountCents > 0 ? amountCents : 0;
    const parts = splitEqually(usable, participantIds.length);
    participantIds.forEach((id, index) => {
      rows[id] = usable > 0 ? centsToInput(parts[index]) : "";
    });
    return rows;
  }

  if (mode === "percentage") {
    // Even percentages that still total exactly 100: thirds become
    // 33,333334 / 33,333333 / 33,333333, not three rounded 33,33s. The visible
    // field carries a comma; `parseScaled` reads it back, and the payload built
    // by `buildParticipantValues` restores the dot the API expects.
    const parts = splitEqually(FULL_PERCENT, participantIds.length);
    participantIds.forEach((id, index) => {
      rows[id] = formatPercentInput(parts[index]).replace(".", ",");
    });
    return rows;
  }

  participantIds.forEach((id) => {
    rows[id] = "1";
  });
  return rows;
}

/** The `participants` payload: null for equal, cents for exact, else the weight. */
export function buildParticipantValues(args: {
  mode: SplitMode;
  participantIds: string[];
  rows: Record<string, string>;
  amounts: Record<string, number>;
}): ParticipantInput[] {
  const { mode, participantIds, rows, amounts } = args;
  return participantIds.map((id) => {
    if (mode === "equal") return { user_id: id, value: null };
    if (mode === "exact") return { user_id: id, value: String(amounts[id] ?? 0) };
    if (mode === "percentage") {
      return {
        user_id: id,
        value: formatPercentInput(parseScaled(rows[id], PERCENT_DECIMALS) ?? 0),
      };
    }
    return { user_id: id, value: String(readShareCount(rows[id])) };
  });
}
