import { Banknote, CalendarDays, Pencil, Trash2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { CategoryIcon } from "@/components/common/CategoryIcon";
import { ConfirmButton } from "@/components/common/ConfirmButton";
import { ErrorState } from "@/components/common/ErrorState";
import { LoadingState } from "@/components/common/LoadingState";
import { UserAvatar } from "@/components/common/UserAvatar";
import { AddExpenseDialog } from "@/components/expenses/AddExpenseDialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useAuth } from "@/hooks/useAuth";
import { useDeleteExpense, useExpense } from "@/hooks/useExpenses";
import { errorMessage } from "@/lib/api";
import { SPLIT_MODES } from "@/lib/constants";
import { formatDate } from "@/lib/format";
import { formatMoney } from "@/lib/money";
import { cn } from "@/lib/utils";
import type { Expense, SplitMode } from "@/types/api";

export interface ExpenseDetailDialogProps {
  expenseId?: string;
  groupId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const MODE_LABELS = Object.fromEntries(
  SPLIT_MODES.map((mode) => [mode.value, mode.label]),
) as Record<SplitMode, string>;

/** Надзаголовок из §2.5 контракта. */
const OVERLINE = "text-[13px] font-bold uppercase tracking-[0.08em] text-dim";

interface Impact {
  headline: string;
  detail: string | null;
  tone: string;
}

/** The sentences a person actually wants: what they put in, what they used. */
function impactOf(expense: Expense, currentUserId: string | undefined): Impact {
  const currency = expense.currency;
  const split = expense.splits.find((item) => item.user_id === currentUserId);
  const shareCents = split?.calculated_amount_cents ?? 0;
  const paidCents = expense.paid_by === currentUserId ? expense.amount_cents : 0;

  if (paidCents === 0 && !split) {
    return {
      headline: "Вы не участвуете в этом расходе.",
      detail: `Сумма расхода — ${formatMoney(expense.amount_cents, currency)}, плательщик — ${expense.payer.name}.`,
      tone: "text-muted-foreground",
    };
  }

  if (paidCents > 0) {
    const net = paidCents - shareCents;
    return {
      headline: `Вы заплатили ${formatMoney(paidCents, currency)}, ваша доля — ${formatMoney(shareCents, currency)}.`,
      detail:
        net > 0
          ? `Группа должна вам ${formatMoney(net, currency)} за этот расход.`
          : "Вы оплатили ровно свою долю.",
      tone: net > 0 ? "text-positive" : "text-muted-foreground",
    };
  }

  return {
    headline: `Плательщик — ${expense.payer.name}: ${formatMoney(expense.amount_cents, currency)}. Ваша доля — ${formatMoney(shareCents, currency)}.`,
    detail:
      shareCents > 0
        ? `Ваш долг по этому расходу — ${formatMoney(shareCents, currency)}.`
        : "В этом расходе на вас ничего не приходится.",
    tone: shareCents > 0 ? "text-negative" : "text-muted-foreground",
  };
}

export function ExpenseDetailDialog({
  expenseId,
  groupId,
  open,
  onOpenChange,
}: ExpenseDetailDialogProps) {
  const { user } = useAuth();
  const expenseQuery = useExpense(open ? expenseId : undefined);
  const deleteExpense = useDeleteExpense(groupId);
  // Snapshotted at click time: the parent usually clears `expenseId` as this
  // dialog closes, and the edit dialog still needs the expense it was opened on.
  const [editing, setEditing] = useState<Expense | undefined>(undefined);

  const expense = expenseQuery.data;

  async function handleDelete(target: Expense) {
    try {
      await deleteExpense.mutateAsync(target.id);
      toast.success("Расход удалён");
      onOpenChange(false);
    } catch (error) {
      toast.error(errorMessage(error));
      // Rethrown so the confirmation stays open behind the toast.
      throw error;
    }
  }

  const impact = expense ? impactOf(expense, user?.id) : null;

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="sm:max-w-[560px]">
          <DialogHeader className="space-y-[5px]">
            <DialogTitle>{expense ? expense.title : "Расход"}</DialogTitle>
            <DialogDescription>
              {expense
                ? `Автор: ${expense.creator.name} · ${MODE_LABELS[expense.split_mode]}`
                : "Загружаем подробности расхода."}
            </DialogDescription>
          </DialogHeader>

          {expenseQuery.isPending ? (
            <LoadingState label="Загружаем расход…" />
          ) : expenseQuery.isError ? (
            <ErrorState
              error={expenseQuery.error}
              onRetry={() => void expenseQuery.refetch()}
            />
          ) : !expense ? (
            <ErrorState error={new Error("Этот расход больше недоступен.")} />
          ) : (
            <div className="mt-2.5 flex flex-col gap-[18px]">
              <div className="rounded-[22px] bg-subtle px-5 py-5 sm:px-6 sm:py-[22px]">
                <span className={OVERLINE}>Сумма расхода</span>
                <p className="mt-2 text-[28px] font-bold leading-none tracking-[-0.03em] text-foreground tabular-nums-money sm:text-[34px]">
                  {formatMoney(expense.amount_cents, expense.currency)}
                </p>
                <div className="mt-[18px] flex flex-wrap items-center gap-2">
                  <Badge variant="neutral" className="gap-[7px] px-[15px] py-2">
                    <CategoryIcon name={expense.category.icon} />
                    {expense.category.name}
                  </Badge>
                  <Badge variant="neutral" className="gap-[7px] px-[15px] py-2">
                    <CalendarDays aria-hidden="true" />
                    {formatDate(expense.occurred_at)}
                  </Badge>
                  <Badge variant="neutral" className="gap-[7px] px-[15px] py-2">
                    <Banknote aria-hidden="true" />
                    Плательщик: {expense.paid_by === user?.id ? "вы" : expense.payer.name}
                  </Badge>
                </div>
              </div>

              {expense.description ? (
                <p className="whitespace-pre-line text-[15px] text-muted-foreground">
                  {expense.description}
                </p>
              ) : null}

              <div className="flex flex-col gap-2.5">
                <p className="text-sm font-semibold text-foreground">Как поделили</p>
                <ul className="overflow-hidden rounded-row bg-subtle">
                  {expense.splits.map((split, index) => (
                    <li
                      key={split.user_id}
                      className={cn(
                        "flex items-center gap-3 px-3 py-3.5 sm:px-[18px]",
                        index > 0 ? "border-t border-border/60" : null,
                      )}
                    >
                      <UserAvatar user={split.user} size="sm" className="size-9" />
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-[15px] font-semibold text-foreground">
                          {split.user.id === user?.id ? "Вы" : split.user.name}
                        </span>
                        {split.user_id === expense.paid_by ? (
                          <span className="mt-px block text-[13px] text-dim">
                            Плательщик
                          </span>
                        ) : null}
                      </span>
                      <span className="whitespace-nowrap text-base font-semibold text-foreground tabular-nums-money">
                        {formatMoney(split.calculated_amount_cents, expense.currency)}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>

              {impact ? (
                <div className="rounded-row bg-subtle px-5 py-4">
                  <p className="text-[15px] text-foreground">{impact.headline}</p>
                  {impact.detail ? (
                    <p className={cn("mt-1 text-[15px] font-semibold", impact.tone)}>
                      {impact.detail}
                    </p>
                  ) : null}
                </div>
              ) : null}

              <div className="mt-2 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end sm:gap-2.5">
                <ConfirmButton
                  title="Удалить расход?"
                  description="Он исчезнет из группы, а балансы участников пересчитаются."
                  confirmLabel="Удалить расход"
                  destructive
                  onConfirm={() => handleDelete(expense)}
                >
                  <Button
                    variant="secondary"
                    size="lg"
                    className="w-full bg-negative-surface text-negative hover:bg-negative-surface-hover hover:text-negative sm:w-auto"
                  >
                    <Trash2 aria-hidden="true" />
                    Удалить
                  </Button>
                </ConfirmButton>
                <Button
                  size="lg"
                  className="w-full sm:w-auto"
                  onClick={() => {
                    setEditing(expense);
                    onOpenChange(false);
                  }}
                >
                  <Pencil aria-hidden="true" />
                  Изменить
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>

      <AddExpenseDialog
        open={Boolean(editing)}
        onOpenChange={(next) => {
          if (!next) setEditing(undefined);
        }}
        groupId={groupId}
        expense={editing}
      />
    </>
  );
}
