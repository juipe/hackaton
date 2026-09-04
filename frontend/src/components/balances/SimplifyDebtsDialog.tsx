import { useEffect, useRef, useState } from "react";
import { ArrowRight, ChevronDown, ChevronUp, ShieldCheck } from "lucide-react";
import { toast } from "sonner";

import { DebtTransferList } from "@/components/balances/DebtTransferList";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { LoadingState } from "@/components/common/LoadingState";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useSimplifyDebts } from "@/hooks/useBalances";
import { errorMessage } from "@/lib/api";
import { plural } from "@/lib/format";
import type { Group, Uuid } from "@/types/api";

export interface SimplifyDebtsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  group: Group;
  currentUserId: Uuid;
}

export function SimplifyDebtsDialog({
  open,
  onOpenChange,
  group,
  currentUserId,
}: SimplifyDebtsDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[640px]">
        <DialogHeader>
          <DialogTitle>Упростить долги</DialogTitle>
          <DialogDescription>
            Короткая дорога к тому же результату. Это рекомендация — «Складчина»
            не переводит деньги и не меняет, кто кому сколько должен.
          </DialogDescription>
        </DialogHeader>

        {/* Mounted only while the dialog is open, so every open fetches a preview
            against the balances as they stand at that moment. */}
        <SimplifyContent
          group={group}
          currentUserId={currentUserId}
          onClose={() => onOpenChange(false)}
        />
      </DialogContent>
    </Dialog>
  );
}

function CloseFooter() {
  return (
    <DialogFooter>
      <DialogClose asChild>
        <Button type="button" variant="secondary" size="lg">
          Закрыть
        </Button>
      </DialogClose>
    </DialogFooter>
  );
}

interface SimplifyContentProps {
  group: Group;
  currentUserId: Uuid;
  onClose: () => void;
}

function SimplifyContent({ group, currentUserId, onClose }: SimplifyContentProps) {
  const preview = useSimplifyDebts(group.id);
  const confirm = useSimplifyDebts(group.id);
  const { mutate: loadPreview } = preview;
  const requested = useRef(false);
  const [showCurrent, setShowCurrent] = useState(false);

  useEffect(() => {
    if (requested.current) return;
    requested.current = true;
    loadPreview(false);
  }, [loadPreview]);

  function handleConfirm() {
    // The same endpoint, now allowed to write the `debt_simplified` activity so
    // the group has a record of the plan everyone agreed to follow.
    confirm.mutate(true, {
      onSuccess: (result) => {
        toast.success(
          `Долги упрощены: ${result.current_transfer_count} → ${plural(
            result.simplified_transfer_count,
            "перевод",
            "перевода",
            "переводов",
          )}`,
        );
        onClose();
      },
      onError: (error) => toast.error(errorMessage(error)),
    });
  }

  if (preview.error) {
    return (
      <div className="mt-[26px] flex flex-col gap-5">
        <ErrorState error={preview.error} onRetry={() => loadPreview(false)} />
        <CloseFooter />
      </div>
    );
  }

  const data = preview.data;
  if (!data) {
    return <LoadingState className="mt-[26px]" label="Ищем самый короткий путь к расчёту…" />;
  }

  const before = data.current_transfer_count;
  const after = data.simplified_transfer_count;
  const saved = Math.max(0, before - after);

  if (before === 0) {
    return (
      <div className="mt-[26px] flex flex-col gap-5">
        <EmptyState
          icon={ShieldCheck}
          title="Все в расчёте"
          description="В группе нет непогашенных долгов — упрощать нечего."
        />
        <CloseFooter />
      </div>
    );
  }

  return (
    <div className="mt-[26px] flex flex-col gap-5">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-3 rounded-row bg-subtle px-[18px] py-4">
        <div className="shrink-0 text-center">
          <p className="text-[28px] font-bold leading-none tracking-[-0.03em] tabular-nums-money">
            {before}
          </p>
          <p className="mt-1.5 text-[13px] text-dim">сейчас</p>
        </div>
        <ArrowRight className="size-[18px] shrink-0 text-dim" aria-hidden="true" />
        <div className="shrink-0 text-center">
          <p className="text-[28px] font-bold leading-none tracking-[-0.03em] tabular-nums-money">
            {after}
          </p>
          <p className="mt-1.5 text-[13px] text-dim">станет</p>
        </div>
        <div className="min-w-0 flex-1 basis-40">
          <p className="text-[15px] font-semibold text-foreground">
            {plural(before, "перевод", "перевода", "переводов")} →{" "}
            {plural(after, "перевод", "перевода", "переводов")}
          </p>
          <p className="mt-0.5 text-[13px] text-dim">
            {saved > 0
              ? `На ${plural(saved, "перевод", "перевода", "переводов")} меньше.`
              : "Группа уже рассчитывается минимальным числом переводов."}
          </p>
        </div>
      </div>

      <div className="flex items-start gap-3 rounded-row bg-subtle p-4">
        <ShieldCheck
          className="mt-0.5 size-[17px] shrink-0 text-dim"
          aria-hidden="true"
        />
        <p className="text-[13px] leading-relaxed text-muted-foreground">
          Итоговый баланс не меняется ни у кого. Каждый по-прежнему остаётся должен —
          или получает — ровно ту же сумму, что и раньше; меняется только то, кто кому
          платит, и это убирает лишние пересылки.
        </p>
      </div>

      <div className="space-y-3">
        <h3 className="text-[19px] font-bold tracking-[-0.02em]">Рекомендуемые переводы</h3>
        <DebtTransferList
          transfers={data.transfers}
          currency={group.currency}
          currentUserId={currentUserId}
        />
      </div>

      <div className="space-y-3">
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="-ml-2"
          onClick={() => setShowCurrent((value) => !value)}
          aria-expanded={showCurrent}
        >
          {showCurrent ? (
            <ChevronUp aria-hidden="true" />
          ) : (
            <ChevronDown aria-hidden="true" />
          )}
          {`${showCurrent ? "Скрыть" : "Показать"} текущие долги (${plural(
            before,
            "перевод",
            "перевода",
            "переводов",
          )})`}
        </Button>
        {showCurrent ? (
          <DebtTransferList
            transfers={data.current_transfers}
            currency={group.currency}
            currentUserId={currentUserId}
          />
        ) : null}
      </div>

      <p className="text-[13px] leading-relaxed text-dim">
        План запишется в ленту группы, чтобы все видели согласованный маршрут. Балансы
        останутся прежними — отмечайте каждый перевод кнопкой «Погасить», когда он
        действительно состоится.
      </p>

      <DialogFooter className="mt-1">
        <DialogClose asChild>
          <Button type="button" variant="secondary" size="lg">
            Отмена
          </Button>
        </DialogClose>
        <Button
          type="button"
          size="lg"
          onClick={handleConfirm}
          disabled={confirm.isPending}
        >
          {confirm.isPending ? "Сохраняем…" : "Принять план"}
        </Button>
      </DialogFooter>
    </div>
  );
}
