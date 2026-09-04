import { RotateCw, TriangleAlert } from "lucide-react";

import { Button } from "@/components/ui/button";
import { errorMessage } from "@/lib/api";
import { cn } from "@/lib/utils";

export interface ErrorStateProps {
  error: unknown;
  onRetry?: () => void;
  className?: string;
}

/**
 * Ошибка выглядит как пустое состояние, только знак в квадрате красный:
 * красная плашка во всю ширину кричала бы громче самой ошибки, а сообщение
 * почти всегда бытовое — «не дозвонились до сервера».
 */
export function ErrorState({ error, onRetry, className }: ErrorStateProps) {
  return (
    <div
      role="alert"
      className={cn(
        "flex flex-col items-center justify-center gap-4 rounded-row bg-subtle px-5 py-9 text-center sm:px-6 sm:py-10",
        className,
      )}
    >
      <span className="flex size-14 shrink-0 items-center justify-center rounded-field bg-muted text-negative">
        <TriangleAlert className="size-6" aria-hidden />
      </span>
      <div className="space-y-1.5">
        <p className="text-[19px] font-bold leading-tight tracking-[-0.02em] text-foreground">
          Не удалось загрузить
        </p>
        <p className="mx-auto max-w-[44ch] text-[15px] leading-relaxed text-muted-foreground [overflow-wrap:anywhere]">
          {errorMessage(error)}
        </p>
      </div>
      {onRetry ? (
        <Button type="button" size="sm" onClick={onRetry}>
          <RotateCw aria-hidden />
          Повторить
        </Button>
      ) : null}
    </div>
  );
}
