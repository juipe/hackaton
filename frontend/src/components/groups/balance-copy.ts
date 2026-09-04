/**
 * Wording for a net balance. Shared by the group card, the group header, the
 * dashboard list and the balances tab so the same number never gets two
 * different labels in two places on the same screen.
 *
 * The phrasings are deliberately impersonal: a name is only ever inserted in the
 * nominative, so nothing here has to be declined or agreed in gender.
 */

import { plural, pluralWord } from "@/lib/format";

/** Label above the amount: «Вам должны» / «Вы должны» / «Долгов нет». */
export function netBalanceLabel(cents: number): string {
  if (cents > 0) return "Вам должны";
  if (cents < 0) return "Вы должны";
  return "Долгов нет";
}

/** The same wording as a caption under an amount, in lower case. */
export function netBalanceCaption(cents: number): string {
  if (cents > 0) return "вам должны";
  if (cents < 0) return "вы должны";
  return "долгов нет";
}

/** Первое предложение под герой-числом на странице группы. */
function netHeadline(cents: number): string {
  if (cents > 0) return "Столько вам должна группа.";
  if (cents < 0) return "Столько вы должны группе.";
  return "Вы со всеми в этой группе рассчитались.";
}

/**
 * Пояснение под балансом группы: что значит число и во сколько переводов
 * закрываются долги.
 *
 * Число переводов стоит в творительном падеже («двумя переводами»), поэтому
 * форма слова берётся через `pluralWord`, а не через `plural`, — иначе рядом
 * оказались бы два числительных в разных падежах.
 */
export function groupBalanceExplainer(
  netCents: number,
  pairwiseCount: number,
  simplifiedCount: number,
): string {
  if (pairwiseCount === 0) return netHeadline(netCents);

  const debts = plural(pairwiseCount, "долг", "долга", "долгов");
  const verb = pluralWord(pairwiseCount, "закрывается", "закрываются", "закрываются");
  const transfers = pluralWord(
    simplifiedCount,
    "переводом",
    "переводами",
    "переводами",
  );
  return `${netHeadline(netCents)} ${debts} ${verb} ${simplifiedCount} ${transfers}.`;
}

/** Счётчик над списком долгов: «3 прямых перевода · после упрощения — 2». */
export function transferCountCaption(
  pairwiseCount: number,
  simplifiedCount: number,
): string {
  const direct = plural(
    pairwiseCount,
    "прямой перевод",
    "прямых перевода",
    "прямых переводов",
  );
  return `${direct} · после упрощения — ${simplifiedCount}`;
}

export interface MemberBalanceCopy {
  /** Имя (или «Вы» / «Вам») — жирная часть строки. Всегда именительный падеж. */
  subject: string;
  /** Состояние — обычным начертанием сразу за именем. */
  state: string;
}

/**
 * Строка участника в списке балансов. Своя строка говорит «Вам должны», чужая —
 * «Костя в минусе»: чужое имя ни в какой падеж ставить не приходится.
 */
export function memberBalanceState(
  cents: number,
  name: string,
  isMe: boolean,
): MemberBalanceCopy {
  if (cents === 0) {
    return { subject: isMe ? "Вы" : name, state: "в расчёте" };
  }
  if (cents > 0) {
    return { subject: isMe ? "Вам" : name, state: isMe ? "должны" : "в плюсе" };
  }
  return { subject: isMe ? "Вы" : name, state: isMe ? "должны" : "в минусе" };
}
