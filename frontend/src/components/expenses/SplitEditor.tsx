import { AlertCircle, Check, Minus, Plus } from "lucide-react";

import { UserAvatar } from "@/components/common/UserAvatar";
import {
  computeSplitPreview,
  formatPercentInput,
  readShareCount,
  seedSplitRows,
  sumPercentMicro,
  sumShareCount,
} from "@/components/expenses/splitMath";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { plural } from "@/lib/format";
import { centsToInput, currencySymbol, formatMoney, splitEqually } from "@/lib/money";
import { cn } from "@/lib/utils";
import type { Member, SplitMode } from "@/types/api";

export { computeSplitPreview } from "@/components/expenses/splitMath";
export type { SplitPreview } from "@/components/expenses/splitMath";

export interface SplitRow {
  userId: string;
  value: string;
}

export interface SplitEditorProps {
  mode: SplitMode;
  amountCents: number;
  currency: string;
  members: Member[];
  participantIds: string[];
  /** userId -> raw input text, exactly as typed. */
  rows: Record<string, string>;
  onRowsChange: (rows: Record<string, string>) => void;
  payerId: string;
  className?: string;
}

const NUMERIC_CHARS = /[^\d.,]/g;

/** Компактное поле внутри строки: белое на подложке --subtle, без обводки. */
const CELL_INPUT =
  "h-10 rounded-xl bg-card px-3 text-right text-sm tabular-nums-money focus-visible:ring-offset-0";

export function SplitEditor({
  mode,
  amountCents,
  currency,
  members,
  participantIds,
  rows,
  onRowsChange,
  payerId,
  className,
}: SplitEditorProps) {
  const preview = computeSplitPreview({ mode, amountCents, participantIds, rows });
  const byUserId = new Map(members.map((member) => [member.user.id, member]));
  const symbol = currencySymbol(currency);
  const hasAmount = amountCents > 0;

  const setValue = (userId: string, value: string) => {
    onRowsChange({ ...rows, [userId]: value });
  };

  const stepShares = (userId: string, delta: number) => {
    setValue(userId, String(Math.max(0, readShareCount(rows[userId]) + delta)));
  };

  const blankExactIds = participantIds.filter((id) => !(rows[id] ?? "").trim());
  const remaining = amountCents - preview.assignedCents;

  const fillExactRest = () => {
    const next = { ...rows };
    if (blankExactIds.length > 0 && remaining > 0) {
      const parts = splitEqually(remaining, blankExactIds.length);
      blankExactIds.forEach((id, index) => {
        next[id] = centsToInput(parts[index]);
      });
    } else {
      const parts = splitEqually(amountCents, participantIds.length);
      participantIds.forEach((id, index) => {
        next[id] = centsToInput(parts[index]);
      });
    }
    onRowsChange(next);
  };

  const resetMode = (target: SplitMode) => {
    onRowsChange(seedSplitRows(target, participantIds, amountCents));
  };

  let action: { label: string; onClick: () => void } | null = null;
  if (mode === "exact") {
    action = {
      label:
        blankExactIds.length > 0 && remaining > 0
          ? "Разделить остаток поровну"
          : "Разделить поровну",
      onClick: fillExactRest,
    };
  } else if (mode === "percentage") {
    action = { label: "Равные проценты", onClick: () => resetMode("percentage") };
  } else if (mode === "shares") {
    action = { label: "По одной доле каждому", onClick: () => resetMode("shares") };
  }

  let hint: string | null = null;
  if (mode === "exact") {
    if (remaining > 0) hint = `осталось распределить ${formatMoney(remaining, currency)}`;
    else if (remaining < 0) hint = `лишние ${formatMoney(-remaining, currency)}`;
  } else if (mode === "percentage") {
    const percent = formatPercentInput(sumPercentMicro(participantIds, rows));
    hint = `сейчас ${percent.replace(".", ",")}%`;
  } else if (mode === "shares") {
    const total = sumShareCount(participantIds, rows);
    if (total !== 0) hint = `сейчас долей: ${String(total).replace(".", ",")}`;
  }

  return (
    <div className={cn("flex flex-col gap-2.5", className)}>
      <div className="flex min-h-8 flex-wrap items-center justify-between gap-x-3 gap-y-1">
        <p className="text-sm font-semibold text-foreground">Доля каждого</p>
        {action ? (
          <Button
            variant="link"
            size="sm"
            className="h-auto p-0 text-[13px]"
            onClick={action.onClick}
            disabled={!hasAmount}
          >
            {action.label}
          </Button>
        ) : null}
      </div>

      <div className="overflow-hidden rounded-row bg-subtle">
        <ul>
          {participantIds.map((userId, index) => {
            const member = byUserId.get(userId);
            const user = member?.user ?? { id: userId, name: "Участник" };
            const amount = preview.amounts[userId] ?? 0;
            return (
              <li
                key={userId}
                className={cn(
                  "flex flex-wrap items-center gap-2.5 px-3 py-3.5 sm:gap-3 sm:px-[18px]",
                  index > 0 ? "border-t border-border/60" : null,
                )}
              >
                <UserAvatar user={user} size="sm" className="size-9" />
                <div
                  className={cn(
                    "min-w-0 flex-1",
                    // Ниже sm имя уходит на отдельную строку: иначе степпер и колонка
                    // суммы съедают всю ширину и от имени остаются считаные пиксели.
                    mode === "equal" ? null : "basis-[calc(100%-46px)] sm:basis-auto",
                  )}
                >
                  <p className="truncate text-[15px] font-semibold text-foreground">
                    {user.name}
                  </p>
                  {userId === payerId ? (
                    <p className="mt-px text-[13px] text-dim">Плательщик</p>
                  ) : null}
                </div>

                {mode === "equal" ? (
                  <span className="shrink-0 text-[13px] text-dim tabular-nums-money">
                    1/{participantIds.length}
                  </span>
                ) : null}

                {mode === "exact" ? (
                  <div className="relative w-[88px] shrink-0 sm:w-[104px]">
                    <Input
                      value={rows[userId] ?? ""}
                      onChange={(event) =>
                        setValue(userId, event.target.value.replace(NUMERIC_CHARS, ""))
                      }
                      inputMode="decimal"
                      autoComplete="off"
                      placeholder="0,00"
                      aria-label={`Точная сумма: ${user.name}`}
                      className={cn(CELL_INPUT, "pr-7")}
                    />
                    <span
                      aria-hidden="true"
                      className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-[13px] text-dim"
                    >
                      {symbol}
                    </span>
                  </div>
                ) : null}

                {mode === "percentage" ? (
                  <div className="relative w-[80px] shrink-0 sm:w-[104px]">
                    <Input
                      value={rows[userId] ?? ""}
                      onChange={(event) =>
                        setValue(userId, event.target.value.replace(NUMERIC_CHARS, ""))
                      }
                      inputMode="decimal"
                      autoComplete="off"
                      placeholder="0"
                      aria-label={`Процент: ${user.name}`}
                      className={cn(CELL_INPUT, "pr-7")}
                    />
                    <span
                      aria-hidden="true"
                      className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-[13px] text-dim"
                    >
                      %
                    </span>
                  </div>
                ) : null}

                {mode === "shares" ? (
                  <div className="flex shrink-0 items-center gap-1">
                    <Button
                      variant="outline"
                      size="icon"
                      className="size-9 shrink-0 [&_svg]:size-4"
                      onClick={() => stepShares(userId, -1)}
                      aria-label={`Убрать долю: ${user.name}`}
                    >
                      <Minus aria-hidden="true" />
                    </Button>
                    <Input
                      value={rows[userId] ?? ""}
                      onChange={(event) =>
                        setValue(userId, event.target.value.replace(/\D/g, ""))
                      }
                      inputMode="numeric"
                      autoComplete="off"
                      placeholder="0"
                      aria-label={`Доли: ${user.name}`}
                      className={cn(CELL_INPUT, "w-11 px-1 text-center")}
                    />
                    <Button
                      variant="outline"
                      size="icon"
                      className="size-9 shrink-0 [&_svg]:size-4"
                      onClick={() => stepShares(userId, 1)}
                      aria-label={`Добавить долю: ${user.name}`}
                    >
                      <Plus aria-hidden="true" />
                    </Button>
                  </div>
                ) : null}

                <span
                  className={cn(
                    "ml-auto shrink-0 whitespace-nowrap text-right text-base font-semibold tabular-nums-money",
                    "w-auto min-w-[88px] sm:min-w-[104px]",
                    hasAmount ? "text-foreground" : "text-dim",
                  )}
                >
                  {formatMoney(amount, currency)}
                </span>
              </li>
            );
          })}
        </ul>

        <div className="flex items-center justify-between gap-3 border-t border-border/60 bg-muted px-3 py-3.5 sm:px-[18px]">
          <span className="text-[13px] font-bold uppercase tracking-[0.06em] text-dim">
            Распределено
          </span>
          <span className="text-right text-base font-bold tabular-nums-money">
            <span className="whitespace-nowrap">
              {formatMoney(preview.assignedCents, currency)}
            </span>
            <span className="block whitespace-nowrap font-medium text-dim sm:ml-1 sm:inline">
              из {formatMoney(Math.max(0, amountCents), currency)}
            </span>
          </span>
        </div>
      </div>

      {!hasAmount ? (
        <p className="text-[13px] text-dim">Укажите сумму выше — и появятся доли каждого.</p>
      ) : preview.error ? (
        <p className="flex items-start gap-2 text-[13px] text-negative">
          <AlertCircle className="mt-px size-[15px] shrink-0" aria-hidden="true" />
          <span>
            {preview.error}
            {hint ? ` — ${hint}` : ""}
          </span>
        </p>
      ) : (
        <p className="flex items-start gap-2 text-[13px] text-accent-foreground">
          <Check className="mt-px size-[15px] shrink-0" aria-hidden="true" />
          <span>
            Сумма сходится: {formatMoney(amountCents, currency)}, в делении{" "}
            {plural(participantIds.length, "человек", "человека", "человек")}.
          </span>
        </p>
      )}
    </div>
  );
}
