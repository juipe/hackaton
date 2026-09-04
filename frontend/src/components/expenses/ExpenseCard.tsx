import { ChevronRight } from "lucide-react";

import { CategoryIcon } from "@/components/common/CategoryIcon";
import { formatMoney } from "@/lib/money";
import { cn } from "@/lib/utils";
import type { Expense } from "@/types/api";

export interface ExpenseCardProps {
  expense: Expense;
  currentUserId: string;
  onSelect?: (expense: Expense) => void;
}

interface Impact {
  label: string;
  tone: string;
}

/**
 * Derived from the splits rather than from the `my_*` fields, so the sentence is
 * still right when the card renders an expense that was fetched for someone else.
 */
function impactOf(expense: Expense, currentUserId: string): Impact {
  const split = expense.splits.find((item) => item.user_id === currentUserId);
  const paidCents = expense.paid_by === currentUserId ? expense.amount_cents : 0;
  if (!split && paidCents === 0) {
    return { label: "вы не участвуете", tone: "text-dim" };
  }
  const net = paidCents - (split?.calculated_amount_cents ?? 0);
  if (net > 0) {
    return {
      label: `вам должны ${formatMoney(net, expense.currency)}`,
      tone: "text-positive",
    };
  }
  if (net < 0) {
    return {
      label: `вы должны ${formatMoney(-net, expense.currency)}`,
      tone: "text-negative",
    };
  }
  return { label: "ровно ваша доля", tone: "text-dim" };
}

/**
 * Строка списка, а не карточка: собственного фона и тени у неё нет — она живёт
 * внутри карточки списка. На узком экране правый блок переносится под название
 * (`flex-wrap`), поэтому на 375px строка не расталкивает страницу вбок.
 */
const SHELL =
  "flex w-full flex-wrap items-center gap-x-4 gap-y-1 rounded-row px-3 py-3.5 text-left transition-colors sm:flex-nowrap sm:px-4";

export function ExpenseCard({ expense, currentUserId, onSelect }: ExpenseCardProps) {
  const impact = impactOf(expense, currentUserId);
  const paidByYou = expense.paid_by === currentUserId;

  const body = (
    <>
      <CategoryIcon
        name={expense.category.icon}
        size="md"
        tone={paidByYou ? "accent" : "muted"}
      />

      <span className="min-w-0 flex-1 basis-[calc(100%-62px)] sm:basis-auto">
        <span className="block truncate text-[17px] font-semibold tracking-[-0.01em] text-foreground">
          {expense.title}
        </span>
        <span className="mt-[3px] block truncate text-sm text-dim">
          {paidByYou ? "Плательщик: вы" : `Плательщик: ${expense.payer.name}`} ·{" "}
          {expense.category.name}
        </span>
      </span>

      <span className="w-full shrink-0 pl-[62px] sm:w-auto sm:pl-0 sm:text-right">
        <span className="block whitespace-nowrap text-[19px] font-bold tracking-[-0.02em] text-foreground tabular-nums-money">
          {formatMoney(expense.amount_cents, expense.currency)}
        </span>
        <span className={cn("mt-[3px] block whitespace-nowrap text-sm", impact.tone)}>
          {impact.label}
        </span>
      </span>

      <ChevronRight
        className="hidden size-[18px] shrink-0 text-faint sm:block"
        strokeWidth={2.2}
        aria-hidden="true"
      />
    </>
  );

  if (!onSelect) {
    return <div className={SHELL}>{body}</div>;
  }

  return (
    <button
      type="button"
      onClick={() => onSelect(expense)}
      aria-label={`Открыть расход «${expense.title}»`}
      className={cn(
        SHELL,
        "hover:bg-subtle focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
      )}
    >
      {body}
    </button>
  );
}
