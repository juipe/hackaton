import { ChevronRight, Users } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { GroupAvatar } from "@/components/common/GroupAvatar";
import { LoadingState } from "@/components/common/LoadingState";
import { ExpenseForm } from "@/components/expenses/ExpenseForm";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useGroups } from "@/hooks/useGroups";
import { plural } from "@/lib/format";
import type { Expense } from "@/types/api";

export interface AddExpenseDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  groupId?: string;
  expense?: Expense;
}

export function AddExpenseDialog({
  open,
  onOpenChange,
  groupId,
  expense,
}: AddExpenseDialogProps) {
  const [pickedGroupId, setPickedGroupId] = useState<string | undefined>(undefined);
  const groupsQuery = useGroups();
  const groups = groupsQuery.data;

  const fixedGroupId = groupId ?? expense?.group_id;
  // One group means there is nothing to choose: skip the step entirely.
  const onlyGroupId = !fixedGroupId && groups?.length === 1 ? groups[0].id : undefined;
  const activeGroupId = fixedGroupId ?? pickedGroupId ?? onlyGroupId;

  // Closing throws the draft away, so reopening never resurrects a half-typed
  // expense for the wrong group.
  useEffect(() => {
    if (!open) setPickedGroupId(undefined);
  }, [open]);

  const activeGroup = groups?.find((group) => group.id === activeGroupId);
  const canChangeGroup =
    !fixedGroupId && Boolean(pickedGroupId) && (groups?.length ?? 0) > 1;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        onOpenAutoFocus={(event) => {
          // The form focuses the amount field itself; letting Radix focus the
          // panel first would steal it back.
          event.preventDefault();
        }}
      >
        <DialogHeader className="space-y-[5px]">
          <DialogTitle>{expense ? "Изменить расход" : "Новый расход"}</DialogTitle>
          <DialogDescription>
            {activeGroupId
              ? activeGroup
                ? `В группе «${activeGroup.name}»`
                : "Укажите сумму и проверьте деление ниже."
              : "В какую группу добавить расход?"}
          </DialogDescription>
          {canChangeGroup ? (
            <Button
              variant="link"
              size="sm"
              className="h-auto justify-start p-0 text-[13px]"
              onClick={() => setPickedGroupId(undefined)}
            >
              Выбрать другую группу
            </Button>
          ) : null}
        </DialogHeader>

        {activeGroupId ? (
          <ExpenseForm
            key={`${activeGroupId}:${expense?.id ?? "new"}`}
            groupId={activeGroupId}
            expense={expense}
            onDone={() => onOpenChange(false)}
            onCancel={() => onOpenChange(false)}
          />
        ) : groupsQuery.isPending ? (
          <LoadingState label="Загружаем ваши группы…" />
        ) : groupsQuery.isError ? (
          <ErrorState error={groupsQuery.error} onRetry={() => void groupsQuery.refetch()} />
        ) : (groups?.length ?? 0) === 0 ? (
          <EmptyState
            icon={Users}
            title="Групп пока нет"
            description="Расходы живут внутри группы. Создайте её и пригласите тех, с кем делите эти расходы."
            action={
              <Button asChild onClick={() => onOpenChange(false)}>
                <Link to="/groups/new">Создать группу</Link>
              </Button>
            }
          />
        ) : (
          <div className="flex flex-col gap-2">
            {(groups ?? []).map((group) => (
              <button
                key={group.id}
                type="button"
                onClick={() => setPickedGroupId(group.id)}
                className="flex w-full items-center gap-3.5 rounded-row bg-subtle px-4 py-3.5 text-left transition-colors hover:bg-subtle-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
              >
                <GroupAvatar group={group} size="sm" />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[15px] font-semibold text-foreground">
                    {group.name}
                  </span>
                  <span className="block text-[13px] text-dim">
                    {plural(group.member_count, "участник", "участника", "участников")}
                  </span>
                </span>
                <ChevronRight className="size-[18px] shrink-0 text-faint" aria-hidden="true" />
              </button>
            ))}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
