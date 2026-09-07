import { AlertTriangle, ChevronRight, Loader2, ReceiptText } from "lucide-react";
import { useEffect, useRef, useState } from "react";

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
import { useCreateReceiptExpenseDraft } from "@/hooks/useReceiptExpense";
import { errorMessage } from "@/lib/api";
import { plural } from "@/lib/format";
import type { VoiceExpenseDraft } from "@/types/api";

export interface ReceiptExpenseDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /**
   * When omitted (opened from the sidebar or the mobile FAB, which have no
   * group context), a group-selection step runs first — the file picker only
   * appears once a group is picked.
   */
  groupId?: string;
}

type Stage = "idle" | "processing" | "review" | "error";

const MAX_RECEIPT_BYTES = 10 * 1024 * 1024;
const ACCEPTED_TYPES = new Set(["image/jpeg", "image/jpg", "image/png"]);

export function ReceiptExpenseDialog({ open, onOpenChange, groupId }: ReceiptExpenseDialogProps) {
  const [pickedGroupId, setPickedGroupId] = useState<string | undefined>(undefined);
  const [stage, setStage] = useState<Stage>("idle");
  const [errorText, setErrorText] = useState<string | null>(null);
  const [draft, setDraft] = useState<VoiceExpenseDraft | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  // Компонент живёт дольше открытия диалога (Radix размонтирует только
  // контент), поэтому «хвост» незавершённой загрузки после закрытия обязан
  // умирать: reset() двигает счётчик, и устаревший ответ не воскрешает review.
  const requestSeq = useRef(0);

  const activeGroupId = groupId ?? pickedGroupId;
  const showGroupPicker = !activeGroupId;
  const groupsQuery = useGroups();

  const createDraft = useCreateReceiptExpenseDraft(activeGroupId ?? "");

  const reset = () => {
    requestSeq.current += 1;
    setErrorText(null);
    setDraft(null);
    setStage("idle");
    if (fileInputRef.current) fileInputRef.current.value = "";
    // Фиксированный groupId (кнопка на странице группы) не требует повторного
    // выбора; глобальный диалог начинает с выбора группы при каждом открытии.
    if (!groupId) setPickedGroupId(undefined);
  };

  useEffect(() => {
    if (!open) reset();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  async function handleFile(file: File) {
    if (!ACCEPTED_TYPES.has(file.type)) {
      setErrorText("Загрузите чек как фото в формате JPEG или PNG.");
      setStage("error");
      return;
    }
    if (file.size > MAX_RECEIPT_BYTES) {
      setErrorText("Фото чека слишком большое — до 10 МБ.");
      setStage("error");
      return;
    }
    const seq = ++requestSeq.current;
    setStage("processing");
    try {
      const result = await createDraft.mutateAsync(file);
      if (seq !== requestSeq.current) return;
      setDraft(result);
      setStage("review");
    } catch (error) {
      if (seq !== requestSeq.current) return;
      setErrorText(errorMessage(error));
      setStage("error");
    }
  }

  const title = showGroupPicker
    ? "Загрузить чек"
    : stage === "review"
      ? "Проверьте расход"
      : stage === "error"
        ? "Не получилось"
        : "Загрузить чек";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className={stage === "review" || showGroupPicker ? undefined : "sm:max-w-[480px]"}
        onOpenAutoFocus={(event) => {
          if (stage === "review" || showGroupPicker) event.preventDefault();
        }}
      >
        <DialogHeader className="space-y-[5px]">
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>
            {showGroupPicker && "В какую группу добавить расход?"}
            {!showGroupPicker && stage === "idle" &&
              "Сфотографируйте или выберите фото чека — распознаем сумму, дату и категорию."}
            {!showGroupPicker && stage === "processing" &&
              "Читаем чек и извлекаем данные о расходе."}
            {!showGroupPicker && stage === "review" &&
              "Проверьте, что мы распознали, и поправьте, что нужно."}
            {!showGroupPicker && stage === "error" && "Можно попробовать ещё раз."}
          </DialogDescription>
        </DialogHeader>

        {showGroupPicker ? (
          <div className="flex flex-col gap-2">
            {groupsQuery.isPending ? (
              <LoadingState label="Загружаем ваши группы…" />
            ) : groupsQuery.isError ? (
              <ErrorState error={groupsQuery.error} onRetry={() => void groupsQuery.refetch()} />
            ) : groupsQuery.data.length === 0 ? (
              <p className="px-1 py-4 text-[15px] text-muted-foreground">
                Групп пока нет — создайте группу, чтобы добавить расход.
              </p>
            ) : (
              groupsQuery.data.map((group) => (
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
              ))
            )}
          </div>
        ) : null}

        {!showGroupPicker && stage === "idle" ? (
          <div className="flex flex-col items-center justify-center gap-5 px-5 py-9 text-center sm:px-6 sm:py-10">
            <input
              ref={fileInputRef}
              type="file"
              accept="image/jpeg,image/png"
              capture="environment"
              className="hidden"
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (file) void handleFile(file);
              }}
            />
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              aria-label="Выбрать фото чека"
              className="flex size-24 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-green transition-transform hover:bg-primary-hover active:scale-95 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
            >
              <ReceiptText className="size-9" aria-hidden="true" />
            </button>
            <p className="max-w-[36ch] text-[15px] text-muted-foreground">
              Нажмите, чтобы сфотографировать чек или выбрать готовое фото. Итоговая
              сумма, дата и категория подставятся сами.
            </p>
          </div>
        ) : null}

        {!showGroupPicker && stage === "processing" ? (
          <div className="flex flex-col items-center justify-center gap-3 px-5 py-9 text-center sm:px-6 sm:py-10">
            <span className="flex size-14 shrink-0 items-center justify-center rounded-field bg-muted text-muted-foreground">
              <Loader2 className="size-6 animate-spin" aria-hidden="true" />
            </span>
            <p className="text-[15px] font-semibold text-foreground">Читаем чек…</p>
            <p className="max-w-[36ch] text-[13px] text-dim">
              Твой AI помощник разбирает фото — обычно это несколько секунд.
            </p>
          </div>
        ) : null}

        {!showGroupPicker && stage === "error" ? (
          <div className="flex flex-col items-center justify-center gap-4 px-5 py-9 text-center sm:px-6 sm:py-10">
            <span className="flex size-14 shrink-0 items-center justify-center rounded-field bg-muted text-negative">
              <AlertTriangle className="size-6" aria-hidden="true" />
            </span>
            <p className="mx-auto max-w-[44ch] text-[15px] leading-relaxed text-muted-foreground [overflow-wrap:anywhere]">
              {errorText}
            </p>
            <Button type="button" size="sm" onClick={reset}>
              Попробовать снова
            </Button>
          </div>
        ) : null}

        {!showGroupPicker && stage === "review" && draft && activeGroupId ? (
          <>
            {draft.warnings.length > 0 ? (
              <ul className="mt-2.5 flex flex-col gap-1.5 rounded-[22px] bg-subtle px-5 py-4 sm:px-6">
                {draft.warnings.map((warning) => (
                  <li key={warning} className="flex items-start gap-2 text-[13px] text-dim">
                    <AlertTriangle className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
                    <span>{warning}</span>
                  </li>
                ))}
              </ul>
            ) : null}
            <ExpenseForm
              groupId={activeGroupId}
              voiceDraft={draft}
              onDone={() => onOpenChange(false)}
              onCancel={() => onOpenChange(false)}
            />
          </>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}
