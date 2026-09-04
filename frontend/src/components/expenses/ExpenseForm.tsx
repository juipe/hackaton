import { AlertCircle, FileText, Loader2 } from "lucide-react";
import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { toast } from "sonner";

import { CategoryIcon } from "@/components/common/CategoryIcon";
import { ErrorState } from "@/components/common/ErrorState";
import { LoadingState } from "@/components/common/LoadingState";
import { UserAvatar } from "@/components/common/UserAvatar";
import { ParticipantSelector } from "@/components/expenses/ParticipantSelector";
import { SplitEditor } from "@/components/expenses/SplitEditor";
import {
  buildParticipantValues,
  computeSplitPreview,
  seedSplitRows,
} from "@/components/expenses/splitMath";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useCategories } from "@/hooks/useCategories";
import { useCreateExpense, useUpdateExpense } from "@/hooks/useExpenses";
import { useAuth } from "@/hooks/useAuth";
import { useGroup, useMembers } from "@/hooks/useGroups";
import { errorMessage } from "@/lib/api";
import { SPLIT_MODES } from "@/lib/constants";
import { dateInputToIso, todayInputValue, toDateInputValue } from "@/lib/format";
import { centsToInput, currencySymbol, parseAmountToCents } from "@/lib/money";
import { cn } from "@/lib/utils";
import type { Expense, ExpenseCreateInput, SplitMode, VoiceExpenseDraft } from "@/types/api";

export interface ExpenseFormProps {
  groupId: string;
  expense?: Expense;
  /**
   * Seeds the draft from a confirmed voice-expense pipeline result instead of
   * blank defaults. Only fields the backend resolved unambiguously are
   * prefilled — anything ambiguous or unresolved is left empty so the
   * existing validation forces an explicit choice here, the same as any
   * manually entered expense. Ignored when `expense` is set.
   */
  voiceDraft?: VoiceExpenseDraft;
  onDone?: () => void;
  /** Rendered as a secondary button next to Save when provided. */
  onCancel?: () => void;
}

interface Draft {
  amountText: string;
  title: string;
  description: string;
  categoryId: string;
  dateValue: string;
  payerId: string;
  participantIds: string[];
  mode: SplitMode;
  rows: Record<string, string>;
}

/** Надзаголовок из §2.5 контракта: 13px / 700 / uppercase / трекинг 0.08em. */
const OVERLINE = "text-[13px] font-bold uppercase tracking-[0.08em] text-dim";

/** `input_value` for an exact split is whole cents; the input shows major units. */
function rowsFromExpense(expense: Expense): Record<string, string> {
  const rows: Record<string, string> = {};
  for (const split of expense.splits) {
    if (expense.split_mode === "equal") {
      rows[split.user_id] = "";
    } else if (expense.split_mode === "exact") {
      rows[split.user_id] = centsToInput(Math.round(Number(split.input_value ?? 0)));
    } else {
      // The API serialises percentages and shares with a dot; the field shows a comma.
      rows[split.user_id] = (split.input_value ?? "").replace(".", ",");
    }
  }
  return rows;
}

export function ExpenseForm({
  groupId,
  expense,
  voiceDraft,
  onDone,
  onCancel,
}: ExpenseFormProps) {
  const { user } = useAuth();
  const membersQuery = useMembers(groupId);
  const categoriesQuery = useCategories();
  const groupQuery = useGroup(groupId);
  const createExpense = useCreateExpense(groupId);
  const updateExpense = useUpdateExpense(expense?.id ?? "", groupId);

  const [draft, setDraft] = useState<Draft | null>(null);
  const [attempted, setAttempted] = useState(false);
  const [showNote, setShowNote] = useState(
    Boolean(expense?.description) || Boolean(voiceDraft?.description),
  );
  const amountRef = useRef<HTMLInputElement>(null);

  const members = membersQuery.data;
  const categories = categoriesQuery.data;
  const group = groupQuery.data;
  const currentUserId = user?.id;

  useEffect(() => {
    if (draft || !members || !categories || !group) return;
    if (expense) {
      setDraft({
        amountText: centsToInput(expense.amount_cents),
        title: expense.title,
        description: expense.description ?? "",
        categoryId: expense.category.id,
        dateValue: toDateInputValue(expense.occurred_at),
        payerId: expense.paid_by,
        participantIds: expense.splits.map((split) => split.user_id),
        mode: expense.split_mode,
        rows: rowsFromExpense(expense),
      });
      return;
    }
    if (voiceDraft) {
      const payerId =
        voiceDraft.payer.status === "resolved" && voiceDraft.payer.value
          ? voiceDraft.payer.value.user.id
          : "";
      const categoryId =
        voiceDraft.category.status === "resolved" && voiceDraft.category.value
          ? voiceDraft.category.value.id
          : "";
      const resolvedParticipantIds = voiceDraft.participants.resolved.map(
        (participant) => participant.member.user.id,
      );
      const participantIds =
        payerId && !resolvedParticipantIds.includes(payerId)
          ? [...resolvedParticipantIds, payerId]
          : resolvedParticipantIds;
      // The row inputs are edited as human-typed decimals with a comma, same
      // as `rowsFromExpense` below — the API (and this draft) use a dot.
      const rows: Record<string, string> =
        voiceDraft.split_mode === "equal"
          ? {}
          : Object.fromEntries(
              voiceDraft.participants.resolved.map((participant) => [
                participant.member.user.id,
                (participant.value ?? "").replace(".", ","),
              ]),
            );
      setDraft({
        amountText:
          voiceDraft.amount_cents !== null ? centsToInput(voiceDraft.amount_cents) : "",
        title: voiceDraft.title ?? "",
        description: voiceDraft.description ?? "",
        categoryId,
        dateValue: voiceDraft.occurred_at ? toDateInputValue(voiceDraft.occurred_at) : todayInputValue(),
        payerId,
        participantIds,
        mode: voiceDraft.split_mode,
        rows,
      });
      return;
    }
    const memberIds = members.map((member) => member.user.id);
    const payerId =
      currentUserId && memberIds.includes(currentUserId)
        ? currentUserId
        : (memberIds[0] ?? "");
    // "Other" is the neutral default, so adding an expense never forces a
    // category decision the user has not made yet.
    const category = categories.find((item) => item.slug === "other") ?? categories[0];
    setDraft({
      amountText: "",
      title: "",
      description: "",
      categoryId: category?.id ?? "",
      dateValue: todayInputValue(),
      payerId,
      participantIds: memberIds,
      mode: "equal",
      rows: {},
    });
  }, [draft, members, categories, group, expense, voiceDraft, currentUserId]);

  const isReady = draft !== null;
  useEffect(() => {
    if (!isReady) return;
    const frame = window.requestAnimationFrame(() => amountRef.current?.focus());
    return () => window.cancelAnimationFrame(frame);
  }, [isReady]);

  const amountCents = draft ? (parseAmountToCents(draft.amountText) ?? 0) : 0;
  const mode = draft?.mode ?? "equal";
  const participantIds = useMemo(
    () => draft?.participantIds ?? [],
    [draft?.participantIds],
  );
  const rows = useMemo(() => draft?.rows ?? {}, [draft?.rows]);

  const preview = useMemo(
    () => computeSplitPreview({ mode, amountCents, participantIds, rows }),
    [mode, amountCents, participantIds, rows],
  );

  const formError = (() => {
    if (!draft) return null;
    if (amountCents <= 0) return "Сумма должна быть больше нуля";
    if (!draft.title.trim()) return "Укажите название";
    if (!draft.categoryId) return "Выберите категорию";
    if (participantIds.length === 0) return "Добавьте хотя бы одного участника";
    if (!participantIds.includes(draft.payerId)) {
      return "Плательщик должен быть среди участников";
    }
    return preview.error;
  })();

  const update = (patch: Partial<Draft>) => {
    setDraft((current) => (current ? { ...current, ...patch } : current));
  };

  const changeMode = (next: SplitMode) => {
    setDraft((current) =>
      current
        ? {
            ...current,
            mode: next,
            rows: seedSplitRows(
              next,
              current.participantIds,
              parseAmountToCents(current.amountText) ?? 0,
            ),
          }
        : current,
    );
  };

  const changeParticipants = (ids: string[]) => {
    setDraft((current) => {
      if (!current) return current;
      const amount = parseAmountToCents(current.amountText) ?? 0;
      // Percentages describe a specific group of people, so changing who is in
      // it invalidates them — reseeding keeps the form submittable.
      if (current.mode === "percentage") {
        return {
          ...current,
          participantIds: ids,
          rows: seedSplitRows("percentage", ids, amount),
        };
      }
      const next: Record<string, string> = {};
      for (const id of ids) {
        const existing = current.rows[id];
        if (existing !== undefined && existing !== "") next[id] = existing;
        else if (current.mode === "shares") next[id] = "1";
        else next[id] = "";
      }
      return { ...current, participantIds: ids, rows: next };
    });
  };

  const changePayer = (payerId: string) => {
    setDraft((current) => {
      if (!current) return current;
      if (current.participantIds.includes(payerId)) return { ...current, payerId };
      const memberIds = (members ?? []).map((member) => member.user.id);
      const participants = memberIds.filter(
        (id) => current.participantIds.includes(id) || id === payerId,
      );
      const amount = parseAmountToCents(current.amountText) ?? 0;
      return {
        ...current,
        payerId,
        participantIds: participants,
        rows:
          current.mode === "percentage"
            ? seedSplitRows("percentage", participants, amount)
            : { ...current.rows, [payerId]: current.mode === "shares" ? "1" : "" },
      };
    });
  };

  const isSaving = createExpense.isPending || updateExpense.isPending;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setAttempted(true);
    if (!draft || formError || isSaving) return;

    const input: ExpenseCreateInput = {
      title: draft.title.trim(),
      description: draft.description.trim() || null,
      amount_cents: amountCents,
      category_id: draft.categoryId,
      paid_by: draft.payerId,
      occurred_at: dateInputToIso(draft.dateValue),
      split_mode: draft.mode,
      participants: buildParticipantValues({
        mode: draft.mode,
        participantIds,
        rows: draft.rows,
        amounts: preview.amounts,
      }),
    };

    try {
      if (expense) {
        await updateExpense.mutateAsync(input);
        toast.success("Расход изменён");
      } else {
        await createExpense.mutateAsync(input);
        toast.success(`Расход «${input.title}» добавлен`);
      }
      onDone?.();
    } catch (error) {
      toast.error(errorMessage(error));
    }
  }

  if (membersQuery.isError || categoriesQuery.isError || groupQuery.isError) {
    return (
      <ErrorState
        error={membersQuery.error ?? categoriesQuery.error ?? groupQuery.error}
        onRetry={() => {
          void membersQuery.refetch();
          void categoriesQuery.refetch();
          void groupQuery.refetch();
        }}
      />
    );
  }

  if (!draft || !members || !categories || !group) {
    return <LoadingState label="Загружаем группу…" />;
  }

  const currency = group.currency;
  const symbol = currencySymbol(currency);
  const activeMode = SPLIT_MODES.find((item) => item.value === draft.mode);
  const activeCategory = categories.find((item) => item.id === draft.categoryId);
  const payer = members.find((member) => member.user.id === draft.payerId)?.user;
  const showErrors = attempted || amountCents > 0;

  return (
    <form onSubmit={handleSubmit} className="flex flex-col" noValidate>
      {/*
        Сумма — герой диалога: не поле, а крупное число на подложке. Обводки нет,
        поэтому фокусное кольцо рисует вся плашка, а не инпут внутри неё.
      */}
      <div className="mt-2.5 rounded-[22px] bg-subtle px-5 py-5 focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-2 focus-within:ring-offset-card sm:px-6 sm:py-[22px]">
        <Label htmlFor="expense-amount" className={OVERLINE}>
          Сумма
        </Label>
        <div className="mt-2 flex items-baseline gap-2">
          <Input
            id="expense-amount"
            ref={amountRef}
            type="text"
            value={draft.amountText}
            onChange={(event) =>
              update({ amountText: event.target.value.replace(/[^\d.,]/g, "") })
            }
            inputMode="decimal"
            autoComplete="off"
            placeholder="0,00"
            className="h-auto min-w-0 flex-1 rounded-none bg-transparent p-0 text-[36px] font-bold leading-none tracking-[-0.035em] tabular-nums-money focus-visible:ring-0 focus-visible:ring-offset-0 sm:text-[44px]"
          />
          <span
            aria-hidden="true"
            className="shrink-0 text-[24px] font-semibold leading-none text-dim sm:text-[30px]"
          >
            {symbol}
          </span>
        </div>
      </div>

      <div className="mt-5 flex flex-col gap-[18px]">
        <div className="space-y-2">
          <Label htmlFor="expense-title">Название</Label>
          <Input
            id="expense-title"
            value={draft.title}
            onChange={(event) => update({ title: event.target.value })}
            maxLength={160}
            placeholder="Продукты на неделю"
            autoComplete="off"
          />
        </div>

        <div className="grid gap-3.5 sm:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="expense-category">Категория</Label>
            <Select
              value={draft.categoryId}
              onValueChange={(value) => update({ categoryId: value })}
            >
              <SelectTrigger
                id="expense-category"
                className="[&>span]:line-clamp-none [&>span]:min-w-0 [&>span]:flex-1"
              >
                <SelectValue placeholder="Выберите категорию">
                  {activeCategory ? (
                    <span className="flex min-w-0 items-center gap-2.5">
                      <CategoryIcon
                        name={activeCategory.icon}
                        className="size-[18px] shrink-0 text-muted-foreground"
                      />
                      <span className="truncate">{activeCategory.name}</span>
                    </span>
                  ) : null}
                </SelectValue>
              </SelectTrigger>
              <SelectContent>
                {categories.map((category) => (
                  <SelectItem key={category.id} value={category.id}>
                    <span className="flex items-center gap-2.5">
                      <CategoryIcon
                        name={category.icon}
                        className="size-[18px] text-muted-foreground"
                      />
                      {category.name}
                    </span>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="expense-date">Дата</Label>
            <Input
              id="expense-date"
              type="date"
              value={draft.dateValue}
              onChange={(event) => update({ dateValue: event.target.value })}
              className="tabular-nums-money"
            />
          </div>
        </div>

        <div className="space-y-2">
          <Label htmlFor="expense-payer">Кто заплатил</Label>
          <Select value={draft.payerId} onValueChange={changePayer}>
            <SelectTrigger
              id="expense-payer"
              className="py-0 pl-2.5 pr-[14px] [&>span]:line-clamp-none [&>span]:min-w-0 [&>span]:flex-1"
            >
              <SelectValue placeholder="Кто заплатил?">
                {payer ? (
                  <span className="flex min-w-0 items-center gap-2.5">
                    <UserAvatar user={payer} size="sm" />
                    <span className="truncate">
                      {payer.id === currentUserId ? `${payer.name} (вы)` : payer.name}
                    </span>
                  </span>
                ) : null}
              </SelectValue>
            </SelectTrigger>
            <SelectContent>
              {members.map((member) => (
                <SelectItem key={member.id} value={member.user.id}>
                  {member.user.id === currentUserId
                    ? `${member.user.name} (вы)`
                    : member.user.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-2.5">
          <Label>Между кем делим</Label>
          <ParticipantSelector
            members={members}
            selectedIds={draft.participantIds}
            onChange={changeParticipants}
            payerId={draft.payerId}
          />
        </div>

        <div className="space-y-2.5">
          <Label>Как делим</Label>
          {/*
            Сегмент, а не вкладки: выбор способа деления меняет содержимое формы
            ниже, но не переключает панели — поэтому здесь обычные кнопки.
            На узком экране капсула складывается в две строки, чтобы «Точные
            суммы» не выдавливали диалог за край.
          */}
          <div
            role="group"
            aria-label="Как делим"
            className="grid grid-cols-2 gap-1 rounded-[24px] bg-subtle p-[5px] sm:flex sm:items-center sm:rounded-full"
          >
            {SPLIT_MODES.map((item) => {
              const active = item.value === draft.mode;
              return (
                <button
                  key={item.value}
                  type="button"
                  aria-pressed={active}
                  onClick={() => changeMode(item.value as SplitMode)}
                  className={cn(
                    "h-10 min-w-0 rounded-full px-2 text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 sm:flex-1",
                    active
                      ? "bg-primary font-bold text-primary-foreground"
                      : "font-medium text-muted-foreground hover:bg-card hover:text-foreground",
                  )}
                >
                  {item.label}
                </button>
              );
            })}
          </div>
          {activeMode ? <p className="text-[13px] text-dim">{activeMode.hint}</p> : null}
        </div>

        <SplitEditor
          mode={draft.mode}
          amountCents={amountCents}
          currency={currency}
          members={members}
          participantIds={draft.participantIds}
          rows={draft.rows}
          onRowsChange={(next) => update({ rows: next })}
          payerId={draft.payerId}
        />

        {showNote ? (
          <div className="space-y-2">
            <Label htmlFor="expense-note">Заметка</Label>
            <Textarea
              id="expense-note"
              value={draft.description}
              onChange={(event) => update({ description: event.target.value })}
              placeholder="Что важно помнить об этом расходе"
              rows={3}
            />
          </div>
        ) : (
          <Button
            variant="ghost"
            size="sm"
            className="h-auto self-start px-0 py-2 text-sm font-semibold text-dim hover:bg-transparent hover:text-accent-foreground [&_svg]:size-4"
            onClick={() => setShowNote(true)}
          >
            <FileText aria-hidden="true" />
            Добавить заметку
          </Button>
        )}

        {showErrors && formError ? (
          <p className="flex items-start gap-2 text-sm text-negative" role="alert">
            <AlertCircle className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
            <span>{formError}</span>
          </p>
        ) : null}
      </div>

      <div className="mt-[26px] flex flex-col-reverse gap-2 sm:flex-row sm:justify-end sm:gap-2.5">
        {onCancel ? (
          <Button
            variant="secondary"
            size="lg"
            onClick={onCancel}
            disabled={isSaving}
            className="w-full sm:w-auto"
          >
            Отмена
          </Button>
        ) : null}
        <Button
          type="submit"
          size="lg"
          disabled={isSaving}
          className="w-full sm:w-auto"
        >
          {isSaving ? <Loader2 className="animate-spin" aria-hidden="true" /> : null}
          {expense ? "Сохранить" : "Добавить расход"}
        </Button>
      </div>
    </form>
  );
}
