import { Loader2 } from "lucide-react";

import { cn } from "@/lib/utils";

export interface LoadingStateProps {
  label?: string;
  className?: string;
}

/**
 * Тот же блок по центру, что и у пустого состояния, — чтобы подмена «загрузка →
 * пусто → ошибка» не двигала вёрстку рывком.
 */
export function LoadingState({ label = "Загрузка…", className }: LoadingStateProps) {
  return (
    <div
      role="status"
      aria-live="polite"
      className={cn(
        "flex flex-col items-center justify-center gap-3 px-5 py-9 text-center sm:px-6 sm:py-10",
        className,
      )}
    >
      <span className="flex size-14 shrink-0 items-center justify-center rounded-field bg-muted text-muted-foreground">
        <Loader2 className="size-6 animate-spin" aria-hidden />
      </span>
      <span className="text-[15px] text-muted-foreground">{label}</span>
    </div>
  );
}
